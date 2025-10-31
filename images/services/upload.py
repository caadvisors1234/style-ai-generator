"""
画像アップロード処理サービス
"""
import os
import uuid
import mimetypes
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile


class UploadValidationError(Exception):
    """アップロードバリデーションエラー"""
    pass


class ImageUploadService:
    """画像アップロード処理サービス"""

    # 許可するファイル形式
    ALLOWED_FORMATS = {'image/jpeg', 'image/png', 'image/webp'}
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

    # ファイルサイズ制限（10MB）
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # 同時アップロード数制限
    MAX_FILES_COUNT = 10

    # サムネイルサイズ
    THUMBNAIL_SIZE = (300, 300)

    def __init__(self, user_id: int):
        """
        初期化

        Args:
            user_id: ユーザーID
        """
        self.user_id = user_id
        self.user_upload_dir = Path(settings.MEDIA_ROOT) / 'uploads' / str(user_id)
        self.user_upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, uploaded_file: UploadedFile) -> None:
        """
        ファイルのバリデーション

        Args:
            uploaded_file: アップロードされたファイル

        Raises:
            UploadValidationError: バリデーションエラー
        """
        # ファイルサイズチェック
        if uploaded_file.size > self.MAX_FILE_SIZE:
            raise UploadValidationError(
                f'ファイルサイズは{self.MAX_FILE_SIZE // (1024*1024)}MB以下にしてください'
            )

        # 拡張子チェック
        file_ext = Path(uploaded_file.name).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise UploadValidationError(
                f'対応していないファイル形式です。対応形式: {", ".join(self.ALLOWED_EXTENSIONS)}'
            )

        # MIMEタイプチェック（緩やかなチェック）
        mime_type = uploaded_file.content_type
        # content_typeが不正確な場合もあるので、拡張子で補完
        guessed_type, _ = mimetypes.guess_type(uploaded_file.name)

        # どちらかが許可されたMIMEタイプであればOK
        if mime_type not in self.ALLOWED_FORMATS and guessed_type not in self.ALLOWED_FORMATS:
            # 拡張子が正しければ許可（ブラウザによってcontent_typeが異なる場合があるため）
            if file_ext not in self.ALLOWED_EXTENSIONS:
                raise UploadValidationError(
                    f'対応していないファイル形式です。対応形式: JPEG, PNG, WebP'
                )

        # 画像ファイルとして開けるか確認
        try:
            img = Image.open(uploaded_file)
            img.verify()
            # ファイルポインタをリセット
            uploaded_file.seek(0)
        except Exception as e:
            raise UploadValidationError(f'画像ファイルとして読み込めません: {str(e)}')

    def validate_files_count(self, files_count: int) -> None:
        """
        ファイル数のバリデーション

        Args:
            files_count: アップロードファイル数

        Raises:
            UploadValidationError: バリデーションエラー
        """
        if files_count > self.MAX_FILES_COUNT:
            raise UploadValidationError(
                f'一度にアップロードできるファイル数は{self.MAX_FILES_COUNT}個までです'
            )

    def generate_unique_filename(self, original_filename: str) -> str:
        """
        UUIDベースのユニークなファイル名を生成

        Args:
            original_filename: 元のファイル名

        Returns:
            ユニークなファイル名
        """
        file_ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex
        return f"{unique_id}{file_ext}"

    def save_file(self, uploaded_file: UploadedFile) -> Dict[str, any]:
        """
        ファイルを保存

        Args:
            uploaded_file: アップロードされたファイル

        Returns:
            保存情報（file_path, file_name, file_size, thumbnail_path）
        """
        # ユニークなファイル名生成
        unique_filename = self.generate_unique_filename(uploaded_file.name)
        file_path = self.user_upload_dir / unique_filename

        # ファイル保存
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # サムネイル生成
        thumbnail_path = self.create_thumbnail(file_path)

        # 相対パスを返す（MEDIA_ROOTからの相対パス）
        relative_file_path = f'uploads/{self.user_id}/{unique_filename}'
        relative_thumbnail_path = f'uploads/{self.user_id}/thumbnails/{Path(thumbnail_path).name}'

        return {
            'file_path': relative_file_path,
            'file_name': uploaded_file.name,
            'file_size': uploaded_file.size,
            'thumbnail_path': relative_thumbnail_path,
        }

    def create_thumbnail(self, image_path: Path) -> Path:
        """
        サムネイル画像を生成

        Args:
            image_path: 元画像のパス

        Returns:
            サムネイル画像のパス
        """
        # サムネイル保存ディレクトリ
        thumbnail_dir = self.user_upload_dir / 'thumbnails'
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        # サムネイルファイル名（常にJPEGで保存）
        thumbnail_filename = f"thumb_{image_path.stem}.jpg"
        thumbnail_path = thumbnail_dir / thumbnail_filename

        # サムネイル生成
        with Image.open(image_path) as img:
            # RGBA画像の場合はRGBに変換
            if img.mode in ('RGBA', 'LA', 'P'):
                # 白背景を作成
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # アスペクト比を維持してリサイズ
            img.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # サムネイル保存（JPEG形式）
            img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)

        return thumbnail_path

    def process_uploads(self, uploaded_files: List[UploadedFile]) -> List[Dict[str, any]]:
        """
        複数ファイルのアップロード処理

        Args:
            uploaded_files: アップロードされたファイルのリスト

        Returns:
            保存情報のリスト

        Raises:
            UploadValidationError: バリデーションエラー
        """
        # ファイル数チェック
        self.validate_files_count(len(uploaded_files))

        results = []
        errors = []

        for uploaded_file in uploaded_files:
            try:
                # バリデーション
                self.validate_file(uploaded_file)

                # ファイル保存
                file_info = self.save_file(uploaded_file)
                results.append(file_info)

            except UploadValidationError as e:
                errors.append({
                    'filename': uploaded_file.name,
                    'error': str(e)
                })
            except Exception as e:
                errors.append({
                    'filename': uploaded_file.name,
                    'error': f'予期しないエラーが発生しました: {str(e)}'
                })

        if errors:
            # エラーがある場合は例外を投げる
            raise UploadValidationError({
                'message': 'アップロード処理中にエラーが発生しました',
                'errors': errors,
                'success_count': len(results)
            })

        return results

    def delete_file(self, file_path: str) -> bool:
        """
        ファイルとサムネイルを削除

        Args:
            file_path: ファイルの相対パス（MEDIA_ROOTからの相対パス）

        Returns:
            削除成功したかどうか
        """
        try:
            # フルパスに変換
            full_path = Path(settings.MEDIA_ROOT) / file_path

            # ファイル削除
            if full_path.exists():
                full_path.unlink()

            # サムネイル削除
            thumbnail_path = full_path.parent / 'thumbnails' / f"thumb_{full_path.name}"
            if thumbnail_path.exists():
                thumbnail_path.unlink()

            return True

        except Exception as e:
            print(f"File deletion error: {str(e)}")
            return False
