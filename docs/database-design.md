# データベース設計書

**作成日**: 2025-10-30
**バージョン**: 1.0
**プロジェクト名**: 美容室画像変換システム
**DBMS**: PostgreSQL 14+

---

## 目次
1. [概要](#概要)
2. [ER図](#er図)
3. [テーブル定義](#テーブル定義)
4. [インデックス設計](#インデックス設計)
5. [制約とトリガー](#制約とトリガー)
6. [データライフサイクル](#データライフサイクル)
7. [セキュリティ設計](#セキュリティ設計)
8. [パフォーマンス最適化](#パフォーマンス最適化)

---

## 概要

### データベース構成
- **DBMS**: PostgreSQL 14以上
- **文字コード**: UTF-8
- **タイムゾーン**: Asia/Tokyo (JST)
- **接続プール**: 推奨（PgBouncer等）

### 設計方針
- Django ORM標準に準拠
- 正規化第3正規形（3NF）を基本とする
- パフォーマンスのため一部非正規化を許容
- ソフトデリート（論理削除）を採用
- 監査ログ（created_at, updated_at）を全テーブルに配置

---

## ER図

```
┌─────────────────┐
│   auth_user     │ (Django標準)
│─────────────────│
│ id (PK)         │
│ username        │
│ password        │
│ email           │
│ is_active       │
│ date_joined     │
└────────┬────────┘
         │
         │ 1:1
         │
┌────────▼────────────────┐
│   UserProfile           │
│─────────────────────────│
│ id (PK)                 │
│ user_id (FK) UNIQUE     │
│ monthly_limit           │
│ monthly_used            │
│ is_deleted              │
│ created_at              │
│ updated_at              │
└────────┬────────────────┘
         │
         │ 1:N
         │
┌────────▼─────────────────────┐
│   ImageConversion            │
│──────────────────────────────│
│ id (PK)                      │
│ user_id (FK)                 │
│ original_image_path          │
│ original_image_name          │
│ original_image_size          │
│ prompt                       │
│ generation_count             │
│ status                       │
│ processing_time              │
│ error_message                │
│ is_deleted                   │
│ created_at                   │
│ updated_at                   │
└────────┬─────────────────────┘
         │
         │ 1:N
         │
┌────────▼─────────────────────┐
│   GeneratedImage             │
│──────────────────────────────│
│ id (PK)                      │
│ conversion_id (FK)           │
│ image_path                   │
│ image_name                   │
│ image_size                   │
│ brightness_adjustment        │
│ expires_at                   │
│ is_deleted                   │
│ created_at                   │
│ updated_at                   │
└──────────────────────────────┘
```

---

## テーブル定義

### 1. auth_user (Django標準テーブル)

Djangoの認証システムが提供する標準のユーザーテーブル。

| カラム名 | データ型 | 制約 | デフォルト値 | 説明 |
|---------|---------|------|------------|------|
| id | BIGSERIAL | PRIMARY KEY | AUTO | ユーザーID |
| username | VARCHAR(150) | UNIQUE, NOT NULL | - | ログインID |
| password | VARCHAR(128) | NOT NULL | - | ハッシュ化パスワード (PBKDF2) |
| email | VARCHAR(254) | NOT NULL | '' | メールアドレス（本システムでは未使用） |
| first_name | VARCHAR(150) | NOT NULL | '' | 名（本システムでは未使用） |
| last_name | VARCHAR(150) | NOT NULL | '' | 姓（本システムでは未使用） |
| is_staff | BOOLEAN | NOT NULL | FALSE | 管理画面アクセス権限 |
| is_active | BOOLEAN | NOT NULL | TRUE | アカウント有効フラグ |
| is_superuser | BOOLEAN | NOT NULL | FALSE | スーパーユーザーフラグ |
| last_login | TIMESTAMP | NULL | NULL | 最終ログイン日時 |
| date_joined | TIMESTAMP | NOT NULL | NOW() | アカウント作成日時 |

**インデックス**:
- `username` (UNIQUE INDEX)

**備考**:
- Django標準のUserモデルをそのまま使用
- パスワードは自動的にPBKDF2でハッシュ化
- 削除は`is_active=False`で論理削除

---

### 2. UserProfile (ユーザープロファイル拡張テーブル)

auth_userを拡張し、本システム固有のユーザー情報を保持。

| カラム名 | データ型 | 制約 | デフォルト値 | 説明 |
|---------|---------|------|------------|------|
| id | BIGSERIAL | PRIMARY KEY | AUTO | プロファイルID |
| user_id | BIGINT | FOREIGN KEY (auth_user.id), UNIQUE, NOT NULL | - | ユーザーID (1:1関係) |
| monthly_limit | INTEGER | NOT NULL, CHECK (monthly_limit >= 0) | 100 | 月間利用可能回数 |
| monthly_used | INTEGER | NOT NULL, CHECK (monthly_used >= 0) | 0 | 当月利用済み回数 |
| is_deleted | BOOLEAN | NOT NULL | FALSE | 論理削除フラグ |
| created_at | TIMESTAMP | NOT NULL | NOW() | 作成日時 |
| updated_at | TIMESTAMP | NOT NULL | NOW() | 更新日時 |

**インデックス**:
- `user_id` (UNIQUE INDEX)
- `is_deleted, created_at` (複合INDEX)

**外部キー制約**:
- `user_id` → `auth_user.id` (ON DELETE CASCADE)

**備考**:
- OneToOneFieldでauth_userと1:1関係
- monthly_used は毎月1日 00:00 (JST) に自動リセット
- 論理削除時は is_deleted=TRUE に設定

**Djangoモデル例**:
```python
from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    monthly_limit = models.IntegerField(default=100)
    monthly_used = models.IntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profile'
        db_table_comment = 'ユーザープロファイル拡張テーブル'
        indexes = [
            models.Index(fields=['is_deleted', 'created_at']),
        ]
```

---

### 3. ImageConversion (画像変換履歴テーブル)

画像変換処理の履歴を記録するメインテーブル。

| カラム名 | データ型 | 制約 | デフォルト値 | 説明 |
|---------|---------|------|------------|------|
| id | BIGSERIAL | PRIMARY KEY | AUTO | 変換ID |
| user_id | BIGINT | FOREIGN KEY (auth_user.id), NOT NULL | - | ユーザーID |
| original_image_path | VARCHAR(500) | NOT NULL | - | 元画像の保存パス |
| original_image_name | VARCHAR(255) | NOT NULL | - | 元画像のファイル名 |
| original_image_size | INTEGER | NOT NULL | - | 元画像のファイルサイズ（バイト） |
| prompt | TEXT | NOT NULL | - | 使用したプロンプト |
| generation_count | INTEGER | NOT NULL, CHECK (generation_count > 0 AND generation_count <= 5) | - | 生成枚数 |
| status | VARCHAR(20) | NOT NULL | 'pending' | 処理ステータス |
| processing_time | DECIMAL(10, 3) | NULL | NULL | 処理時間（秒） |
| error_message | TEXT | NULL | NULL | エラーメッセージ |
| is_deleted | BOOLEAN | NOT NULL | FALSE | 論理削除フラグ |
| created_at | TIMESTAMP | NOT NULL | NOW() | 作成日時 |
| updated_at | TIMESTAMP | NOT NULL | NOW() | 更新日時 |

**ステータス値**:
- `pending`: 処理待ち
- `processing`: 処理中
- `completed`: 完了
- `failed`: 失敗
- `cancelled`: キャンセル済み（ユーザーがキャンセルした変換。ギャラリーからは除外される）

**インデックス**:
- `user_id, created_at DESC` (複合INDEX)
- `status, created_at` (複合INDEX)
- `is_deleted, created_at DESC` (複合INDEX)

**外部キー制約**:
- `user_id` → `auth_user.id` (ON DELETE CASCADE)

**備考**:
- 1回の変換処理ごとに1レコード作成
- processing_timeは処理完了時に記録
- エラー時はerror_messageに詳細を記録
- 30日経過後に自動的に論理削除

**Djangoモデル例**:
```python
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class ImageConversion(models.Model):
    STATUS_CHOICES = [
        ('pending', '処理待ち'),
        ('processing', '処理中'),
        ('completed', '完了'),
        ('failed', '失敗'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversions'
    )
    original_image_path = models.CharField(max_length=500)
    original_image_name = models.CharField(max_length=255)
    original_image_size = models.IntegerField()
    prompt = models.TextField()
    generation_count = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    processing_time = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True
    )
    error_message = models.TextField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'image_conversion'
        db_table_comment = '画像変換履歴テーブル'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['is_deleted', '-created_at']),
        ]
```

---

### 4. GeneratedImage (生成画像テーブル)

AI生成された画像を管理するテーブル。

| カラム名 | データ型 | 制約 | デフォルト値 | 説明 |
|---------|---------|------|------------|------|
| id | BIGSERIAL | PRIMARY KEY | AUTO | 生成画像ID |
| conversion_id | BIGINT | FOREIGN KEY (ImageConversion.id), NOT NULL | - | 変換履歴ID |
| image_path | VARCHAR(500) | NOT NULL | - | 生成画像の保存パス |
| image_name | VARCHAR(255) | NOT NULL | - | 生成画像のファイル名 |
| image_size | INTEGER | NOT NULL | - | 画像ファイルサイズ（バイト） |
| brightness_adjustment | INTEGER | NOT NULL, CHECK (brightness_adjustment >= -50 AND brightness_adjustment <= 50) | 0 | 輝度調整値 (-50〜+50) |
| expires_at | TIMESTAMP | NOT NULL | created_at + INTERVAL '30 days' | 削除予定日時 |
| is_deleted | BOOLEAN | NOT NULL | FALSE | 論理削除フラグ |
| created_at | TIMESTAMP | NOT NULL | NOW() | 作成日時 |
| updated_at | TIMESTAMP | NOT NULL | NOW() | 更新日時 |

**インデックス**:
- `conversion_id, created_at` (複合INDEX)
- `expires_at, is_deleted` (複合INDEX) - 自動削除処理用
- `is_deleted, created_at DESC` (複合INDEX)

**外部キー制約**:
- `conversion_id` → `ImageConversion.id` (ON DELETE CASCADE)

**備考**:
- 1回の変換でgeneration_count分のレコードが作成される
- expires_atは作成日から30日後に自動設定
- brightness_adjustment はデフォルト0（調整なし）
- 自動削除ジョブが expires_at を基準に削除処理を実行

**Djangoモデル例**:
```python
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.validators import MinValueValidator, MaxValueValidator

class GeneratedImage(models.Model):
    conversion = models.ForeignKey(
        'ImageConversion',
        on_delete=models.CASCADE,
        related_name='generated_images'
    )
    image_path = models.CharField(max_length=500)
    image_name = models.CharField(max_length=255)
    image_size = models.IntegerField()
    brightness_adjustment = models.IntegerField(
        default=0,
        validators=[MinValueValidator(-50), MaxValueValidator(50)]
    )
    expires_at = models.DateTimeField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # expires_atを自動設定
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'generated_image'
        db_table_comment = '生成画像テーブル'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversion', 'created_at']),
            models.Index(fields=['expires_at', 'is_deleted']),
            models.Index(fields=['is_deleted', '-created_at']),
        ]
```

---

## インデックス設計

### 基本方針
- 頻繁に使用される検索条件にインデックスを付与
- 複合インデックスは選択度の高いカラムを先頭に配置
- 更新頻度の高いテーブルではインデックスを最小限に
- EXPLAIN ANALYZEで定期的にパフォーマンス検証

### インデックス一覧

#### UserProfile
```sql
CREATE INDEX idx_user_profile_is_deleted_created
ON user_profile (is_deleted, created_at);
```

#### ImageConversion
```sql
CREATE INDEX idx_image_conversion_user_created
ON image_conversion (user_id, created_at DESC);

CREATE INDEX idx_image_conversion_status_created
ON image_conversion (status, created_at);

CREATE INDEX idx_image_conversion_is_deleted_created
ON image_conversion (is_deleted, created_at DESC);
```

#### GeneratedImage
```sql
CREATE INDEX idx_generated_image_conversion_created
ON generated_image (conversion_id, created_at);

CREATE INDEX idx_generated_image_expires_deleted
ON generated_image (expires_at, is_deleted);

CREATE INDEX idx_generated_image_is_deleted_created
ON generated_image (is_deleted, created_at DESC);
```

---

## 制約とトリガー

### CHECK制約

#### UserProfile
```sql
ALTER TABLE user_profile
ADD CONSTRAINT check_monthly_limit_positive
CHECK (monthly_limit >= 0);

ALTER TABLE user_profile
ADD CONSTRAINT check_monthly_used_positive
CHECK (monthly_used >= 0);
```

#### ImageConversion
```sql
ALTER TABLE image_conversion
ADD CONSTRAINT check_generation_count_range
CHECK (generation_count > 0 AND generation_count <= 5);

ALTER TABLE image_conversion
ADD CONSTRAINT check_status_valid
CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled'));
```

#### GeneratedImage
```sql
ALTER TABLE generated_image
ADD CONSTRAINT check_brightness_range
CHECK (brightness_adjustment >= -50 AND brightness_adjustment <= 50);
```

### トリガー (updated_at自動更新)

```sql
-- 更新日時自動更新関数
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- UserProfile用トリガー
CREATE TRIGGER trigger_user_profile_updated_at
BEFORE UPDATE ON user_profile
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- ImageConversion用トリガー
CREATE TRIGGER trigger_image_conversion_updated_at
BEFORE UPDATE ON image_conversion
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- GeneratedImage用トリガー
CREATE TRIGGER trigger_generated_image_updated_at
BEFORE UPDATE ON generated_image
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();
```

---

## データライフサイクル

### 1. 月間利用回数リセット

**実行タイミング**: 毎月1日 00:00 (JST)
**実行方法**: Celery Beat + Django管理コマンド

```python
# management/commands/reset_monthly_usage.py
from django.core.management.base import BaseCommand
from accounts.models import UserProfile

class Command(BaseCommand):
    help = '月間利用回数をリセット'

    def handle(self, *args, **options):
        updated = UserProfile.objects.filter(
            is_deleted=False
        ).update(monthly_used=0)

        self.stdout.write(
            self.style.SUCCESS(f'{updated}件のユーザーをリセットしました')
        )
```

### 2. 期限切れ画像の自動削除

**実行タイミング**: 毎日 02:00 (JST)
**実行方法**: Celery Beat + Django管理コマンド

```python
# management/commands/delete_expired_images.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from images.models import GeneratedImage, ImageConversion
import os

class Command(BaseCommand):
    help = '期限切れ画像を削除'

    def handle(self, *args, **options):
        now = timezone.now()

        # 期限切れの生成画像を取得
        expired_images = GeneratedImage.objects.filter(
            expires_at__lt=now,
            is_deleted=False
        )

        deleted_count = 0
        for image in expired_images:
            # 物理ファイル削除
            if os.path.exists(image.image_path):
                os.remove(image.image_path)

            # 論理削除
            image.is_deleted = True
            image.save()
            deleted_count += 1

        # 関連する変換履歴も論理削除
        # (すべての生成画像が削除された変換履歴)
        ImageConversion.objects.filter(
            generated_images__is_deleted=True,
            is_deleted=False
        ).exclude(
            generated_images__is_deleted=False
        ).update(is_deleted=True)

        self.stdout.write(
            self.style.SUCCESS(f'{deleted_count}件の画像を削除しました')
        )
```

### 3. Celery Beat設定

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'reset-monthly-usage': {
        'task': 'accounts.tasks.reset_monthly_usage',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),
        'options': {'timezone': 'Asia/Tokyo'}
    },
    'delete-expired-images': {
        'task': 'images.tasks.delete_expired_images',
        'schedule': crontab(hour=2, minute=0),
        'options': {'timezone': 'Asia/Tokyo'}
    },
}
```

---

## セキュリティ設計

### 1. データアクセス制御

#### ユーザー権限管理
- 一般ユーザー: 自分のデータのみアクセス可能
- スタッフ: 管理画面アクセス可能
- スーパーユーザー: 全データアクセス可能

#### Djangoでの実装例
```python
# views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

@login_required
def gallery_view(request):
    # ユーザーは自分の画像のみ閲覧可能
    conversions = ImageConversion.objects.filter(
        user=request.user,
        is_deleted=False
    )
    return render(request, 'gallery.html', {'conversions': conversions})

@login_required
def download_image(request, image_id):
    image = get_object_or_404(GeneratedImage, id=image_id)

    # 権限チェック
    if image.conversion.user != request.user:
        raise PermissionDenied("このファイルへのアクセス権限がありません")

    # ダウンロード処理...
```

### 2. SQLインジェクション対策

- Django ORM使用（パラメータバインド自動適用）
- 生SQLは極力避ける
- 必要な場合は必ずパラメータ化クエリを使用

```python
# 良い例
User.objects.filter(username=user_input)

# 悪い例（絶対に使用しない）
# User.objects.raw(f"SELECT * FROM auth_user WHERE username = '{user_input}'")
```

### 3. パスワード管理

- Django標準のPBKDF2ハッシュ化
- ソルト自動付与
- パスワードポリシー: 最小8文字

```python
# settings.py
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}
    },
]
```

### 4. ファイルアクセス制御

```python
# ファイル保存時のパス生成
import uuid
from pathlib import Path

def upload_image_path(instance, filename):
    # ユーザーIDごとにディレクトリ分離
    ext = Path(filename).suffix
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"uploads/user_{instance.user.id}/{new_filename}"
```

---

## パフォーマンス最適化

### 1. クエリ最適化

#### select_related / prefetch_related の活用

```python
# 悪い例: N+1問題
conversions = ImageConversion.objects.filter(user=request.user)
for conversion in conversions:
    print(conversion.user.username)  # 毎回DB問い合わせ

# 良い例: select_related使用
conversions = ImageConversion.objects.filter(
    user=request.user
).select_related('user')

# 良い例: prefetch_related使用（1:N関係）
conversions = ImageConversion.objects.filter(
    user=request.user
).prefetch_related('generated_images')
```

#### only / defer の活用

```python
# 必要なカラムだけ取得
conversions = ImageConversion.objects.only(
    'id', 'prompt', 'created_at', 'status'
)

# 大きいカラムを除外
conversions = ImageConversion.objects.defer('error_message')
```

### 2. バルク操作の活用

```python
# 悪い例
for image in images:
    image.is_deleted = True
    image.save()

# 良い例
GeneratedImage.objects.filter(
    expires_at__lt=timezone.now()
).update(is_deleted=True)
```

### 3. データベース接続プール

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'image_conversion_db',
        'USER': 'db_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'CONN_MAX_AGE': 600,  # 接続プール（秒）
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

### 4. キャッシュ戦略

```python
from django.core.cache import cache

# ユーザーの利用可能回数をキャッシュ
def get_user_remaining_count(user_id):
    cache_key = f'user_remaining_{user_id}'
    remaining = cache.get(cache_key)

    if remaining is None:
        profile = UserProfile.objects.get(user_id=user_id)
        remaining = profile.monthly_limit - profile.monthly_used
        cache.set(cache_key, remaining, timeout=300)  # 5分間キャッシュ

    return remaining
```

---

## バックアップ戦略

### 1. PostgreSQLバックアップ

```bash
#!/bin/bash
# 日次バックアップスクリプト

BACKUP_DIR="/var/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="image_conversion_db"

# フルバックアップ
pg_dump -U postgres -d $DB_NAME | gzip > "$BACKUP_DIR/backup_$DATE.sql.gz"

# 7日以上前のバックアップを削除
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete
```

### 2. 画像ファイルバックアップ

```bash
#!/bin/bash
# 画像ファイルの日次バックアップ

MEDIA_DIR="/var/www/media"
BACKUP_DIR="/var/backups/media"
DATE=$(date +%Y%m%d)

# rsyncで増分バックアップ
rsync -av --delete $MEDIA_DIR $BACKUP_DIR/media_$DATE/
```

---

## マイグレーション管理

### 初期マイグレーション作成

```bash
# モデル作成後
python manage.py makemigrations

# マイグレーション適用
python manage.py migrate

# マイグレーション確認
python manage.py showmigrations
```

### カスタムマイグレーション例

```python
# migrations/0002_create_indexes.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('images', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY idx_image_conversion_user_created
            ON image_conversion (user_id, created_at DESC);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_image_conversion_user_created;
            """
        ),
    ]
```

---

## データ整合性チェック

### 定期実行推奨のチェック項目

1. **孤立レコードチェック**
```sql
-- 削除されたユーザーの画像が残っていないか
SELECT * FROM image_conversion ic
WHERE NOT EXISTS (
    SELECT 1 FROM auth_user u WHERE u.id = ic.user_id
);
```

2. **利用回数整合性チェック**
```sql
-- monthly_usedとactual countの差異確認
SELECT
    up.user_id,
    up.monthly_used as recorded_count,
    COUNT(gi.id) as actual_count
FROM user_profile up
LEFT JOIN image_conversion ic ON up.user_id = ic.user_id
    AND EXTRACT(MONTH FROM ic.created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
    AND EXTRACT(YEAR FROM ic.created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
LEFT JOIN generated_image gi ON ic.id = gi.conversion_id
WHERE up.is_deleted = FALSE
GROUP BY up.user_id, up.monthly_used
HAVING up.monthly_used != COUNT(gi.id);
```

3. **期限切れ画像チェック**
```sql
-- 削除されるべきだが残っている画像
SELECT * FROM generated_image
WHERE expires_at < NOW() AND is_deleted = FALSE;
```

---

## 付録

### A. テーブル作成SQL（参考）

```sql
-- UserProfile
CREATE TABLE user_profile (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    monthly_limit INTEGER NOT NULL DEFAULT 100 CHECK (monthly_limit >= 0),
    monthly_used INTEGER NOT NULL DEFAULT 0 CHECK (monthly_used >= 0),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE user_profile IS 'ユーザープロファイル拡張テーブル';

-- ImageConversion
CREATE TABLE image_conversion (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    original_image_path VARCHAR(500) NOT NULL,
    original_image_name VARCHAR(255) NOT NULL,
    original_image_size INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    generation_count INTEGER NOT NULL CHECK (generation_count > 0 AND generation_count <= 5),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    processing_time DECIMAL(10, 3),
    error_message TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE image_conversion IS '画像変換履歴テーブル';

-- GeneratedImage
CREATE TABLE generated_image (
    id BIGSERIAL PRIMARY KEY,
    conversion_id BIGINT NOT NULL REFERENCES image_conversion(id) ON DELETE CASCADE,
    image_path VARCHAR(500) NOT NULL,
    image_name VARCHAR(255) NOT NULL,
    image_size INTEGER NOT NULL,
    brightness_adjustment INTEGER NOT NULL DEFAULT 0 CHECK (brightness_adjustment >= -50 AND brightness_adjustment <= 50),
    expires_at TIMESTAMP NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE generated_image IS '生成画像テーブル';
```

---

**文書履歴**:
- 2025-10-30: 初版作成
- 2025-11-01: cancelledステータスを追加、CHECK制約を更新
