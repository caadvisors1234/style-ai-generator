"""
HotPepper Beautyスクレイピングサービス
"""
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import ParseResult, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile

from .upload import ImageUploadService, UploadValidationError


logger = logging.getLogger(__name__)


class ScraperValidationError(Exception):
    """
    スクレイピング時のバリデーション例外
    """


class HPBScraperService:
    """
    HotPepper Beautyから画像を取得しアップロードするサービス
    """

    ALLOWED_DOMAIN = "beauty.hotpepper.jp"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    REQUEST_TIMEOUT = 10

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.upload_service = ImageUploadService(user_id=user_id)

    def scrape_and_upload(self, url: str) -> List[Dict[str, Any]]:
        """
        指定されたHotPepper Beautyページから画像を取得し、アップロードする
        """
        parsed_url, page_type = self._validate_url(url)

        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("HotPepper Beautyページの取得に失敗しました: %s", url, exc_info=exc)
            raise ScraperValidationError(
                "ページの読み込みに失敗しました。URLが正しいか確認してください。"
            ) from exc

        soup = BeautifulSoup(response.content, "html.parser")
        base_url = response.url or url

        image_urls = self._extract_image_urls(page_type, soup, base_url)
        if not image_urls:
            raise ScraperValidationError("指定されたURLから画像を見つけることができませんでした。")

        uploaded_files = self._download_images(image_urls)
        if not uploaded_files:
            raise ScraperValidationError("指定されたURLから画像を見つけることができませんでした。")

        max_files = getattr(self.upload_service, "MAX_FILES_COUNT", 10)
        if len(uploaded_files) > max_files:
            logger.info(
                "ダウンロードした画像が上限を超えたためトリミングします: %s -> %s",
                len(uploaded_files),
                max_files,
            )
            uploaded_files = uploaded_files[:max_files]

        try:
            return self.upload_service.process_uploads(uploaded_files)
        except UploadValidationError as exc:
            logger.error("画像の保存処理でエラーが発生しました", exc_info=exc)
            raise ScraperValidationError("画像の保存処理でエラーが発生しました。") from exc

    def _validate_url(self, url: str) -> Tuple[ParseResult, str]:
        """
        HPB URLバリデーション
        """
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            raise ScraperValidationError("有効なHotPepper BeautyのURLを入力してください。") from exc

        if parsed.scheme not in {"http", "https"} or parsed.netloc != self.ALLOWED_DOMAIN:
            raise ScraperValidationError("有効なHotPepper BeautyのURLを入力してください。")

        page_type = self._determine_page_type(parsed.path)
        if not page_type:
            raise ScraperValidationError("対応しているのはスタイル、スタイリスト、ブログページのみです。")

        return parsed, page_type

    def _determine_page_type(self, path: str) -> str:
        segments = [segment for segment in path.split("/") if segment]
        for idx, segment in enumerate(segments):
            if segment == "style" and idx + 1 < len(segments) and segments[idx + 1].startswith("L"):
                return "style"
            if segment == "stylist" and idx + 1 < len(segments) and segments[idx + 1].startswith("T"):
                return "stylist"
            if segment == "blog" and idx + 1 < len(segments) and segments[idx + 1].startswith("bidA"):
                return "blog"
        return ""

    def _extract_image_urls(
        self,
        page_type: str,
        soup: BeautifulSoup,
        base_url: str,
    ) -> List[str]:
        """
        ページタイプ別に画像URLを抽出
        """
        strategy_map = {
            "style": self._extract_style_image,
            "stylist": self._extract_stylist_image,
            "blog": self._extract_blog_images,
        }

        strategy = strategy_map.get(page_type)
        if not strategy:
            return []

        image_urls = strategy(soup)
        normalized_urls = []

        for image_url in image_urls:
            if not image_url:
                continue
            normalized_urls.append(self._normalize_image_url(image_url, base_url))

        return [url for url in normalized_urls if url]

    def _normalize_image_url(self, image_url: str, base_url: str) -> str:
        """
        画像URLを絶対パス化し、クエリを取り除く
        """
        absolute_url = urljoin(base_url, image_url)
        parsed = urlparse(absolute_url)
        clean_url = parsed._replace(query="", fragment="").geturl()
        return clean_url

    def _extract_style_image(self, soup: BeautifulSoup) -> List[str]:
        target = soup.select_one('img[name="main"]')
        if not target:
            return []
        return [target.get("src")]

    def _extract_stylist_image(self, soup: BeautifulSoup) -> List[str]:
        target = soup.select_one("div.fl.w245.taC > div > img")
        if not target:
            return []
        return [target.get("src")]

    def _extract_blog_images(self, soup: BeautifulSoup) -> List[str]:
        nodes = soup.select("dl.blogDtlInner dd img")
        return [node.get("src") for node in nodes if node.get("src")]

    def _download_images(self, image_urls: List[str]) -> List[SimpleUploadedFile]:
        """
        画像URLからデータをダウンロードし SimpleUploadedFile に変換
        """
        files: List[SimpleUploadedFile] = []

        for index, image_url in enumerate(image_urls):
            try:
                response = requests.get(
                    image_url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=self.REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("画像のダウンロードに失敗しました: %s", image_url, exc_info=exc)
                continue

            filename = Path(urlparse(image_url).path).name or f"hpb_image_{index}.jpg"
            content_type = (
                response.headers.get("Content-Type")
                or mimetypes.guess_type(filename)[0]
                or "image/jpeg"
            )

            files.append(SimpleUploadedFile(filename, response.content, content_type))

        return files
