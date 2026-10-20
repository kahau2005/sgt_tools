"""LibreWolf link checker used by the desktop application."""

import os
import re
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit


BLOCKED_PHRASES = (
    "this content isn't available",
    "this post isn't available",
    "content not found",
    "the link you followed may be broken",
    "bạn hiện không xem được nội dung này",
    "nội dung này hiện không xem được",
    "bài viết không còn khả dụng",
    "liên kết này có thể đã hỏng",
    "trang bạn yêu cầu không tìm thấy",
    "nội dung không có sẵn",
    "you can't see this content",
)


class LinkCheckResult:
    def __init__(
        self,
        result: str,
        reason: str,
        reload_count: int = 0,
        interactions: int = 0,
        comments: int = 0,
        shares: int = 0,
    ):
        self.result = result
        self.reason = reason
        self.reload_count = reload_count
        self.interactions = interactions
        self.comments = comments
        self.shares = shares


class GroupCheckResult:
    def __init__(
        self,
        result: str,
        reason: str,
        group_url: str = "",
        alt_url: str = "",
        group_name: str = "",
        member_count: int | None = None,
        group_type: str = "",
    ):
        self.result = result
        self.reason = reason
        self.group_url = group_url
        self.alt_url = alt_url
        self.group_name = group_name
        self.member_count = member_count
        self.group_type = group_type


class LibreWolfChecker:
    CHECK_TIMEOUT_SECONDS = 10
    MAX_TIMEOUT_RETRIES = 3
    MAX_GROUP_RETRIES = 3

    def __init__(
        self,
        stop_event: threading.Event,
        profile_path: str | None = None,
        headless: bool | None = None,
        librewolf_dir: str | None = None,
    ):
        self.stop_event = stop_event
        self.driver = None
        self._load_runtime_defaults()
        if librewolf_dir:
            self._load_librewolf_dir(librewolf_dir)
        else:
            raise ValueError("Chưa chọn thư mục LibreWolf.")
        if profile_path:
            self.profile = profile_path
        if headless is not None:
            self.headless = headless

    def _load_runtime_defaults(self):
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resource_root = getattr(sys, "_MEIPASS", app_root)
        candidates = (
            os.path.join(resource_root, "geckodriver.exe"),
            os.path.join(app_root, "geckodriver.exe"),
        )
        self.geckodriver = next(
            (os.path.abspath(path) for path in candidates if os.path.isfile(path)),
            None,
        )
        if not self.geckodriver:
            raise FileNotFoundError(
                "Không tìm thấy geckodriver.exe cạnh ứng dụng."
            )
        self.page_timeout = self.CHECK_TIMEOUT_SECONDS
        self.verdict_timeout = self.CHECK_TIMEOUT_SECONDS
        self.binary = None
        self.profile = None
        self.headless = False

    def _load_librewolf_dir(self, directory: str):
        directory = os.path.abspath(os.path.expanduser(directory))
        candidates = [directory]
        try:
            candidates.extend(
                os.path.join(directory, name)
                for name in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, name))
            )
        except OSError as exc:
            raise FileNotFoundError(
                f"Không thể đọc thư mục LibreWolf: {directory}"
            ) from exc

        for candidate in candidates:
            binary = os.path.join(candidate, "LibreWolf", "librewolf.exe")
            profile = os.path.join(candidate, "Profiles", "Default")
            if os.path.isfile(binary) and os.path.isdir(profile):
                self.binary = os.path.abspath(binary)
                self.profile = os.path.abspath(profile)
                return
        raise FileNotFoundError(
            "Thư mục đã chọn không chứa LibreWolf và profile Default hợp lệ."
        )

    def start(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

        options = Options()
        options.binary_location = self.binary
        options.page_load_strategy = "eager"
        options.add_argument("-profile")
        options.add_argument(self.profile)
        if self.headless:
            options.add_argument("-headless")
        options.set_preference("browser.shell.checkDefaultBrowser", False)
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("permissions.default.desktop-notification", 2)
        self.driver = webdriver.Firefox(
            service=Service(self.geckodriver),
            options=options,
        )
        self.driver.set_page_load_timeout(self.page_timeout)

    def stop(self):
        driver = self.driver
        self.driver = None
        if not driver:
            return

        def quit_driver():
            try:
                driver.quit()
            except Exception:
                pass

        # Firefox can occasionally block while shutting down. Do not hold the
        # check worker (and therefore the next Odoo batch) for that shutdown.
        shutdown_thread = threading.Thread(target=quit_driver, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=2.0)

    def check(self, url: str, timeout_seconds: float | None = None) -> LinkCheckResult:
        from selenium.common.exceptions import TimeoutException

        if timeout_seconds is not None:
            self.page_timeout = timeout_seconds
            self.verdict_timeout = timeout_seconds
            if self.driver:
                self.driver.set_page_load_timeout(timeout_seconds)

        last_result = None
        reload_count = 0
        for attempt in range(self.MAX_TIMEOUT_RETRIES):
            if self.stop_event.is_set():
                return LinkCheckResult("stopped", "STOPPED_BY_USER")

            if attempt == 0:
                last_result = self._check_once(url, load_page=True)
            else:
                try:
                    self.driver.refresh()
                except TimeoutException:
                    reload_count += 1
                    last_result = LinkCheckResult(
                        "error", "TIMEOUT_KHONG_XAC_DINH", reload_count
                    )
                except Exception as exc:
                    return LinkCheckResult("error", f"DRIVER_ERROR: {exc}")
                else:
                    time.sleep(0.5)
                    reload_count += 1
                    last_result = self._check_once(
                        url, load_page=False, reload_count=reload_count
                    )

            if last_result.result != "error" or last_result.reason != "TIMEOUT_KHONG_XAC_DINH":
                return last_result

            if attempt < self.MAX_TIMEOUT_RETRIES - 1:
                time.sleep(0.5)

        return last_result or LinkCheckResult(
            "error", "TIMEOUT_KHONG_XAC_DINH", reload_count
        )

    def check_group(
        self, url: str, alt_url: str = "", timeout_seconds: float | None = None
    ) -> GroupCheckResult:
        from selenium.common.exceptions import TimeoutException

        if timeout_seconds is not None:
            self.page_timeout = timeout_seconds
            self.verdict_timeout = timeout_seconds
            if self.driver:
                self.driver.set_page_load_timeout(timeout_seconds)
        candidates = [value.strip() for value in (url, alt_url) if value and value.strip()]
        if not candidates:
            return GroupCheckResult("DEAD", "GROUP_URL_EMPTY")
        last_error = "GROUP_NOT_AVAILABLE"
        for candidate in candidates:
            if self.stop_event.is_set():
                return GroupCheckResult("STOPPED", "STOPPED_BY_USER")
            for attempt in range(1, self.MAX_GROUP_RETRIES + 1):
                if self.stop_event.is_set():
                    return GroupCheckResult("STOPPED", "STOPPED_BY_USER")
                try:
                    self.driver.execute_script("window.__gbAboutClicked = false;")
                    self.driver.get(candidate)
                except TimeoutException:
                    try:
                        self.driver.execute_script("window.stop();")
                    except Exception:
                        pass
                    last_error = "TIMEOUT_KHONG_XAC_DINH"
                    if attempt < self.MAX_GROUP_RETRIES:
                        time.sleep(0.8)
                        continue
                    return GroupCheckResult("TIMEOUT", last_error)
                except Exception as exc:
                    last_error = f"DRIVER_ERROR: {exc}"
                    return GroupCheckResult("ERROR", last_error)
                result = self._inspect_group_page(candidate)
                if result.result == "ALIVE":
                    return result
                if result.result in {"PARTIAL", "DEAD", "TIMEOUT"}:
                    last_error = result.reason
                    if attempt < self.MAX_GROUP_RETRIES:
                        time.sleep(0.8)
                        continue
                    return result
                return result
        return GroupCheckResult("ERROR", last_error)

    def _inspect_group_page(self, source_url: str) -> GroupCheckResult:
        deadline = time.monotonic() + self.verdict_timeout
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return GroupCheckResult("STOPPED", "STOPPED_BY_USER")
            try:
                current_url, data, about_clicked = self.driver.execute_script(
                    """
                    const aboutTerms = ['about', 'giới thiệu', 'gioi thieu'];
                    let aboutClicked = false;
                    for (const element of document.querySelectorAll(
                      'a,button,[role="button"],[role="tab"]'
                    )) {
                      const label = (
                        element.innerText || element.getAttribute('aria-label') || ''
                      ).trim().toLowerCase();
                      const selected = element.getAttribute('aria-selected') === 'true'
                        || element.classList.contains('selected');
                      if (!window.__gbAboutClicked && !selected
                        && aboutTerms.some((term) => label === term || label.includes(term))) {
                        element.click();
                        window.__gbAboutClicked = true;
                        aboutClicked = true;
                        break;
                      }
                    }
                    const text = document.body ? document.body.innerText : "";
                    const visible = (el) => {
                      if (!el) return false;
                      const r = el.getBoundingClientRect();
                      return r.width > 0 && r.height > 0;
                    };
                    const labels = Array.from(document.querySelectorAll(
                      'a,button,[role="button"],h1,h2,h3'
                    )).filter(visible).map((el) => ({
                      text: (el.innerText || el.getAttribute("aria-label") || "").trim(),
                      href: el.href || ""
                    }));
                    const title = document.title || '';
                    const metaTitle = document.querySelector('meta[property="og:title"]');
                    const heading = document.querySelector('h1');
                    const canonical = document.querySelector('link[rel="canonical"]');
                    const ogUrl = document.querySelector('meta[property="og:url"]');
                    const groupUrls = Array.from(document.querySelectorAll('a[href]'))
                      .map((link) => link.href || '')
                      .filter((href) => /\/groups\/[^/?#]+/i.test(href));
                    return [
                      location.href,
                      {
                        text,
                        labels,
                        title,
                        metaTitle: (metaTitle && metaTitle.content) || '',
                        heading: (heading && heading.innerText) || '',
                        canonical: (canonical && canonical.href) || '',
                        ogUrl: (ogUrl && ogUrl.content) || '',
                        groupUrls
                      },
                      aboutClicked
                    ];
                    """
                )
                if about_clicked:
                    time.sleep(0.8)
                    continue
                body = (data.get("text") or "").strip()
                lowered = body.casefold()
                if any(phrase in lowered for phrase in BLOCKED_PHRASES):
                    return GroupCheckResult("DEAD", "BI_CHAN_HOAC_DA_XOA")
                if any(part in current_url.casefold() for part in ("/login", "checkpoint")):
                    return GroupCheckResult("ERROR", "SESSION_LOGIN_CHECKPOINT")
                if len(body) < 80:
                    time.sleep(0.5)
                    continue
                labels = data.get("labels") or []
                texts = [str(item.get("text") or "").strip() for item in labels]
                group_name = _clean_group_title(data.get("title"))
                if not group_name:
                    group_name = _clean_group_title(
                        (data.get("metaTitle") or "")
                    )
                if not group_name:
                    group_name = _clean_group_title(data.get("heading"))
                if not group_name:
                    group_name = next(
                        (text for text in texts
                         if 3 <= len(text) <= 160
                         and text.casefold() not in {"about", "giới thiệu", "gioi thieu"}),
                        "",
                    )
                group_urls = data.get("groupUrls") or []
                current_alt_url = _normalize_text_group_url(current_url)
                source_alt_url = _normalize_text_group_url(source_url)
                discovered_alt_url = next(
                    (
                        _normalize_text_group_url(href)
                        for href in (
                            group_urls
                            + [data.get("canonical") or "", data.get("ogUrl") or ""]
                        )
                        if _is_text_group_url(href)
                    ),
                    "",
                )
                if current_alt_url and current_alt_url != source_alt_url:
                    discovered_alt_url = current_alt_url
                member_count = None
                member_match = re.search(
                    r"([\d.,]+(?:\s*[KkMm])?)\s*(?:members|thành viên)",
                    body,
                    re.I,
                )
                if member_match:
                    member_count = _parse_member_count(member_match.group(1))
                group_type = ""
                type_match = re.search(
                    r"\b(public|private|công khai|riêng tư|buy\s*&?\s*sell)\b",
                    body,
                    re.I,
                )
                if type_match:
                    group_type = _normalize_group_type(type_match.group(1))
                result = "ALIVE" if group_name and member_count is not None else "PARTIAL"
                return GroupCheckResult(
                    result,
                    "OK" if result == "ALIVE" else "THIEU_THONG_TIN",
                    source_url,
                    (
                        discovered_alt_url
                        or (
                            _normalize_text_group_url(current_url)
                            if current_url != source_url and _is_text_group_url(current_url)
                            else ""
                        )
                    ),
                    group_name,
                    member_count,
                    group_type,
                )
            except Exception:
                time.sleep(0.5)
        return GroupCheckResult("TIMEOUT", "TIMEOUT_KHONG_XAC_DINH")

    def _check_once(
        self, url: str, load_page: bool, reload_count: int = 0
    ) -> LinkCheckResult:
        from selenium.common.exceptions import TimeoutException

        kind, target, post_id = parse_link(url)
        if kind in {"unknown", "group_only"} or not post_id:
            return LinkCheckResult("dead", "LINK_KHONG_CO_POST_ID")
        if self.stop_event.is_set():
            return LinkCheckResult("stopped", "STOPPED_BY_USER")

        if load_page:
            try:
                self.driver.get(target)
            except TimeoutException:
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    pass
                return LinkCheckResult(
                    "error", "TIMEOUT_KHONG_XAC_DINH", reload_count
                )
            except Exception as exc:
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    return LinkCheckResult("error", f"DRIVER_ERROR: {exc}")

        deadline = time.monotonic() + self.verdict_timeout
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return LinkCheckResult("stopped", "STOPPED_BY_USER")
            try:
                current_url = (self.driver.current_url or "").lower()
                body_text = (self.driver.find_element("tag name", "body").text or "").lower()
            except Exception:
                time.sleep(0.5)
                continue

            if any(phrase in body_text for phrase in BLOCKED_PHRASES):
                return LinkCheckResult("dead", "BI_CHAN_HOAC_DA_XOA")
            if any(part in current_url for part in ("/login", "checkpoint", "recover")):
                return LinkCheckResult("error", "SESSION_LOGIN_CHECKPOINT")
            state, interactions, comments, shares = self._inspect_post(post_id, body_text)
            if state == "blocked":
                return LinkCheckResult("dead", "BI_CHAN_HOAC_DA_XOA")
            if state == "alive":
                return LinkCheckResult(
                    "alive",
                    "OK",
                    reload_count=reload_count,
                    interactions=interactions,
                    comments=comments,
                    shares=shares,
                )
            time.sleep(0.5)

        return LinkCheckResult("error", "TIMEOUT_KHONG_XAC_DINH", reload_count)

    def _inspect_post(self, post_id: str, body_text: str) -> tuple[str, int, int, int]:
        """Confirm the post URL and extract meaningful rendered page content & engagement metrics."""
        try:
            res = self.driver.execute_script(
                """
                const postId = String(arguments[0] || '').toLowerCase();
                const bodyText = String(arguments[1] || '').trim();
                const visible = (element) => {
                    if (!element) return false;
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    return rect.width > 180 && rect.height > 80
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const roots = [];
                document.querySelectorAll('div[role="dialog"]').forEach((element) => {
                    if (visible(element)) roots.push(element);
                });
                const main = document.querySelector('div[role="main"]');
                if (visible(main)) roots.push(main);
                if (!roots.length && document.body) roots.push(document.body);

                let hasPost = false;
                for (const root of roots) {
                    for (const article of root.querySelectorAll('div[role="article"]')) {
                        if (!visible(article)) continue;
                        const text = (article.innerText || '').toLowerCase();
                        const hasTarget = postId && Array.from(
                            article.querySelectorAll('a[href]')
                        ).some((link) => String(link.href || '').toLowerCase().includes(postId));
                        const labels = Array.from(
                            article.querySelectorAll('[role="button"], button')
                        ).map((element) => (
                            (element.getAttribute('aria-label') || '') + ' ' +
                            (element.innerText || '')
                        ).toLowerCase());
                        const hasAction = labels.some((label) =>
                            label.includes('like') || label.includes('thích')
                        ) && labels.some((label) =>
                            label.includes('comment') || label.includes('bình luận') ||
                            label.includes('share') || label.includes('chia sẻ')
                        );
                        if (hasTarget || hasAction || text.length > 80) {
                            hasPost = true;
                            break;
                        }
                    }
                    if (hasPost) break;
                }
                const currentUrl = String(location.href || '').toLowerCase();
                const onPostUrl = currentUrl.includes(postId) || currentUrl.includes('/posts/');
                const meaningfulBody = bodyText.length >= 180;
                const isAlive = onPostUrl && (hasPost || meaningfulBody);

                let rawInteractions = '';
                let rawComments = '';
                let rawShares = '';

                if (isAlive) {
                    // Find the target article element
                    let targetArticle = null;
                    for (const root of roots) {
                        const articles = Array.from(root.querySelectorAll('div[role="article"]')).filter(visible);
                        for (const art of articles) {
                            const hasTarget = postId && Array.from(art.querySelectorAll('a[href]'))
                                .some((link) => String(link.href || '').toLowerCase().includes(postId));
                            if (hasTarget) {
                                targetArticle = art;
                                break;
                            }
                        }
                        if (targetArticle) break;
                        if (articles.length === 1) {
                            targetArticle = articles[0];
                            break;
                        }
                    }
                    if (!targetArticle && roots.length) {
                        targetArticle = roots[0];
                    }

                    if (targetArticle) {
                        // 1. Reactions: only look at reaction elements / buttons (never read post body text!)
                        const allButtons = Array.from(targetArticle.querySelectorAll('[role="button"], button, [role="toolbar"]'));
                        for (const el of allButtons) {
                            const label = (el.getAttribute('aria-label') || '').toLowerCase().trim();
                            const text = (el.innerText || '').trim();

                            const isReactionContainer = label.includes('bày tỏ cảm xúc') ||
                                                         label.includes('reacted to this') ||
                                                         label.includes('ai đã thích') ||
                                                         label.includes('cảm xúc') ||
                                                         label.includes('reactions') ||
                                                         label.includes('lượt thích') ||
                                                         label.includes('người khác');

                            if (isReactionContainer) {
                                // If innerText is purely digits or digits + K/M (e.g. "3", "15", "1.2K")
                                if (/^[\d.,]+\s*[km]?$/i.test(text)) {
                                    rawInteractions = text;
                                    break;
                                }
                                // Check label for "X người khác"
                                const mOthers = label.match(/([\d.,]+(?:\s*[km])?)\s*người khác/i);
                                if (mOthers) {
                                    const baseVal = parseFloat(mOthers[1].replace(',', '.'));
                                    const hasAnd = label.includes(' và ') || label.includes(' and ');
                                    const commaCount = (label.match(/,/g) || []).length;
                                    const namedUsers = commaCount + (hasAnd ? 1 : 0);
                                    rawInteractions = String(namedUsers + baseVal);
                                    break;
                                }
                                // Check label for direct count like "15 cảm xúc" or "15 reactions"
                                const mCount = label.match(/([\d.,]+(?:\s*[km])?)\s*(?:cảm xúc|reactions?|lượt thích|likes?)/i);
                                if (mCount) {
                                    rawInteractions = mCount[1];
                                    break;
                                }
                            }
                        }

                        // Check reaction icons container if button aria-label wasn't present
                        if (!rawInteractions) {
                            const reactionIcons = targetArticle.querySelectorAll('img[src*="reaction"], [aria-label="Thích"], [aria-label="Like"], [aria-label="Yêu thích"], [aria-label="Love"]');
                            for (const icon of reactionIcons) {
                                const container = icon.closest('[role="button"]') || icon.parentElement;
                                if (container && container !== targetArticle) {
                                    const cText = (container.innerText || '').trim();
                                    if (/^[\d.,]+\s*[km]?$/i.test(cText)) {
                                        rawInteractions = cText;
                                        break;
                                    }
                                }
                            }
                        }

                        // 2. Comments and Shares: must strictly match standalone count format
                        const textElements = Array.from(targetArticle.querySelectorAll('span, div[role="button"], a[role="link"], button'));
                        for (const el of textElements) {
                            const text = (el.innerText || '').trim();
                            const label = (el.getAttribute('aria-label') || '').trim();
                            const candidate = text || label;

                            if (!rawComments) {
                                const mComm = candidate.match(/^([\d.,]+(?:\s*[km])?)\s*(?:bình luận|câu trả lời|comments?|replies)$/i);
                                if (mComm) {
                                    rawComments = mComm[1];
                                }
                            }
                            if (!rawShares) {
                                const mShare = candidate.match(/^([\d.,]+(?:\s*[km])?)\s*(?:lượt chia sẻ|chia sẻ|shares?)$/i);
                                if (mShare) {
                                    rawShares = mShare[1];
                                }
                            }
                            if (rawComments && rawShares) break;
                        }
                    }
                }

                return {
                    state: isAlive ? 'alive' : 'waiting',
                    rawInteractions: rawInteractions || '',
                    rawComments: rawComments || '',
                    rawShares: rawShares || ''
                };
                """,
                post_id,
                body_text,
            )
            if not isinstance(res, dict):
                return "waiting", 0, 0, 0
            state = res.get("state") or "waiting"
            interactions = _parse_engagement_metric(res.get("rawInteractions"))
            comments = _parse_engagement_metric(res.get("rawComments"))
            shares = _parse_engagement_metric(res.get("rawShares"))
            return state, interactions, comments, shares
        except Exception:
            return "waiting", 0, 0, 0


_PATH_PATTERNS = (
    r"/groups/[^/]+/posts/(\d+)",
    r"/groups/[^/]+/permalink/(\d+)",
)
_QUERY_KEYS = ("multi_permalinks", "multi_permalink", "permalink", "story_fbid", "fbid")


def parse_link(url: str):
    value = (url or "").strip()
    if not value:
        return "unknown", value, None
    parsed = urlparse(value)
    group_match = re.search(r"/groups/([^/?&#]+)", parsed.path)
    group_id = group_match.group(1) if group_match else None
    for pattern in _PATH_PATTERNS:
        match = re.search(pattern, parsed.path)
        if match and group_id:
            post_id = match.group(1)
            return "permalink", f"https://www.facebook.com/groups/{group_id}/posts/{post_id}/", post_id
    query = parse_qs(parsed.query)
    for key in _QUERY_KEYS:
        values = query.get(key)
        if values and values[0].isdigit() and group_id:
            post_id = values[0]
            return "multi", f"https://www.facebook.com/groups/{group_id}/posts/{post_id}/", post_id
    if group_id:
        return "group_only", value, None
    return "unknown", value, None


def _parse_member_count(value: str) -> int | None:
    text = value.strip().replace(" ", "")
    multiplier = 1
    if text.casefold().endswith("k"):
        multiplier, text = 1000, text[:-1]
    elif text.casefold().endswith("m"):
        multiplier, text = 1000000, text[:-1]
    if multiplier > 1:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "").replace(".", "")
    try:
        return int(float(text.replace(",", ".")) * multiplier)
    except ValueError:
        return None


def _parse_engagement_metric(value) -> int:
    """Parse Facebook engagement counts (e.g. '12', '1.2K', '3,5M') into non-negative integers."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = str(value).strip().replace(" ", "")
    if not text:
        return 0
    multiplier = 1
    if text.casefold().endswith("k"):
        multiplier, text = 1000, text[:-1]
    elif text.casefold().endswith("m"):
        multiplier, text = 1000000, text[:-1]
    if multiplier > 1:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return max(0, int(float(text) * multiplier))
    except (ValueError, TypeError):
        return 0


def _normalize_group_type(value: str) -> str:
    """Return the Odoo selection key for a Facebook group type."""
    normalized = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return {
        "public": "public",
        "public group": "public",
        "công khai": "public",
        "private": "private",
        "private group": "private",
        "riêng tư": "private",
        "buy & sell": "buy_sell",
        "buy&sell": "buy_sell",
        "buy sell": "buy_sell",
    }.get(normalized, "")


def _clean_group_title(value: str) -> str:
    title = str(value or "").strip()
    if not title:
        return ""
    title = re.sub(r"^\(\d+\+?\)\s*", "", title)
    title = re.split(r"\s*\|\s*Facebook\b", title, maxsplit=1, flags=re.I)[0]
    title = re.sub(r"\s*[|·-]\s*Facebook(?:\s+Groups?)?\s*$", "", title, flags=re.I)
    if title.casefold() in {"facebook", "facebook groups"}:
        return ""
    return title.strip(" -|·")


def _is_text_group_url(value: str) -> bool:
    match = re.search(r"/groups/([^/?#]+)", urlparse(value).path)
    return bool(match and not match.group(1).isdigit())


def _normalize_text_group_url(value: str) -> str:
    """Return only the canonical text-ID group URL, without /about or tabs."""
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    segments = [segment for segment in parsed.path.split("/") if segment]
    lowered = [segment.casefold() for segment in segments]
    try:
        group_index = lowered.index("groups")
        identifier = segments[group_index + 1]
    except (ValueError, IndexError):
        return ""
    if not identifier or identifier.isdigit():
        return ""
    hostname = (parsed.hostname or "").lower()
    if hostname in {"facebook.com", "m.facebook.com", "web.facebook.com"}:
        hostname = "www.facebook.com"
    return urlunsplit(("https", hostname, f"/groups/{identifier}", "", ""))
