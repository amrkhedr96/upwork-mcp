# Upwork agent

```
https://github.com/amrkhedr96/upwork-mcp
```

سيرفر وأدوات ومهارة واحدة. Cursor و Claude و Codex بيفتحوا نفس السيرفر. كل شخص يربط حساب Upwork بتاعه. الوكيل يدور على الشغل، يحلّل، يكتب العرض، ويقدّم لما الشخص يقول «ابعت».

## التشغيل

المطلوب: Python 3.11 وبرنامج `uv`.

```powershell
git clone https://github.com/amrkhedr96/upwork-mcp.git
cd upwork-mcp
uv run python install.py
```

الأمر الأخير ينسخ المهارة إلى مجلدات Cursor و Codex و Claude على نفس الجهاز.

## الربط

بدّل المسار بمسار المجلد بعد النسخ. بعد اللصق، اقفل العميل وافتحه تاني.

Cursor. الملف:

```
%USERPROFILE%\.cursor\mcp.json
```

```json
"upwork": {
  "command": "uv",
  "args": ["--directory", "C:\\path\\to\\upwork-mcp", "run", "server.py"]
}
```

Codex. الملف:

```
%USERPROFILE%\.codex\config.toml
```

```toml
[mcp_servers.upwork]
command = "uv"
args = ["--directory", "C:\\path\\to\\upwork-mcp", "run", "server.py"]
```

Claude، من جوه المجلد، أو بالأمر ده:

```powershell
claude mcp add upwork -- uv --directory C:\path\to\upwork-mcp run server.py
```

Claude يقدر يقرأ الملف ده لو العميل مفتوح على المجلد:

```
.mcp.json
```

## حساب Upwork

1. اطلب مفتاح OAuth 2.0 من هنا:

```
https://www.upwork.com/developer/keys/apply
```

2. النوع: Web project. رابط الرجوع:

```
https://www.upwork.com/ab/messages/rooms/
```

3. علّم الصلاحيات دي: Common Entities، Read marketplace Job Postings، Submit Proposal، Client Proposals، Messaging، Offer.

4. قول للوكيل يحفظ معرّف العميل والسر. السر يتسجل هنا ومايترجعش في الشات:

```
%USERPROFILE%\.upwork-mcp\config.json
```

5. افتح لينك الموافقة، وافق، وابعث قيمة `code` من الرابط. التوكن يتسجل هنا:

```
%USERPROFILE%\.upwork-mcp\token.json
```

6. قول نوع الشغل المطلوب. الوكيل يدور ويحلّل ويعرض المسودة. التقديم يتم بعد «ابعت».

## الأدوات

| الأداة | الوظيفة |
|---|---|
| `upwork_status` | المفتاح والتوكن موجودين ولا لأ |
| `upwork_save_credentials` | حفظ معرّف العميل والسر |
| `upwork_auth_url` | لينك الموافقة |
| `upwork_exchange_code` | تحويل الكود إلى توكن |
| `upwork_whoami` | بيانات الحساب |
| `upwork_search_jobs` | البحث عن وظائف |
| `upwork_job` | قراءة وظيفة |
| `upwork_list_proposals` | قائمة العروض |
| `upwork_proposal` | عرض واحد |
| `upwork_list_rooms` | غرف الشات |
| `upwork_room_messages` | رسائل غرفة |
| `upwork_list_contracts` | العقود |
| `upwork_submit_proposal` | تقديم. يصرف Connects فقط مع `confirm=true` |
| `upwork_send_message` | إرسال رسالة. نفس شرط التأكيد |
| `upwork_export_excel` | ملف Excel |

## فحص سريع

```powershell
uv run python -m unittest tests.test_workbook tests.test_upwork_client
```
