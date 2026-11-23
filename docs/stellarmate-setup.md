<div dir="rtl">

# إعداد StellarMate و Ekos

السكربتات في `ekos/roof` يشغّلها درايفر INDI اسمه **Dome Scripting Gateway**. Ekos يعتبر السقف "قبة"، فـ **Unpark** يعني فتح السقف، و**Park** يعني إغلاقه.

| في Ekos | السكربت | ماذا يحدث |
|---|---|---|
| Connect | `connect.py` | يتأكد أن الـ ESP يرد |
| Unpark | `unpark.py` | يرسل **فتح** (ولا يرسله لو السقف مفتوح أو يفتح) |
| Park | `park.py` | يرسل **إغلاق** |
| Abort | `abort.py` | يرسل **إيقاف** (يُتجاهل لو السقف واقف) |
| Status | `status.py` | كل ثانيتين: هل السقف مفتوح بالكامل؟ |

## 1) نسخ المجلد إلى StellarMate

المكان الصحيح: **`/home/stellarmate/roof`**، وليس سطح المكتب.

**من الكمبيوتر** (Mac أو Linux، أو PowerShell في Windows):
```bash
scp -r ekos-roof-controller/ekos/roof stellarmate@stellarmate.local:~/
```
كلمة سر StellarMate الافتراضية `smate`.

**أو بفلاشة / مدير الملفات:** انسخ مجلد `roof` إلى StellarMate، ثم انقله من Terminal:
```bash
[ -d ~/roof ] && mv ~/roof ~/roof_old; mv ~/Desktop/roof ~/roof
ls ~/roof          # يجب أن ترى roof_config.py و install.sh ومجلد scripts
```

## 2) التثبيت

```bash
cd ~/roof && bash install.sh
```
يطلب كلمة سر StellarMate. ماذا يفعل:
- يثبّت OpenCV وffmpeg، وهما للكاميرا (اختيارية).
- يجعل السكربتات قابلة للتشغيل.
- يجهّز خدمة مراقبة الكاميرا `roof-monitor`، ولا يشغّلها.

## 3) الإعدادات: `roof_config.py`

```bash
kate ~/roof/roof_config.py      # محرر بالماوس
# أو
nano ~/roof/roof_config.py      # حفظ: Ctrl+O ثم Enter، خروج: Ctrl+X
```
> **عبر RustDesk أو VNC** قد لا تعمل اختصارات Ctrl في nano. استخدم **F3** للحفظ و**F2** للخروج، أو استخدم `kate`.

عدّل هذه الأسطر:
```python
SWITCH_TYPE = "esp"
ESP_HOST = "192.168.100.115"   # عنوان الـ ESP
ESP_USER = "admin"             # نفس web_user في secrets.yaml
ESP_PASS = "..."               # نفس web_password في secrets.yaml
STATUS_SOURCE = "esp"          # "esp" أو "camera"
```

**من يؤكد لـ Ekos أن السقف مفتوح؟ الإعداد `STATUS_SOURCE`:**
- **القيمة `"esp"`:** الموقع المحسوب بالوقت في الـ ESP. يعمل فوراً، لكن لو علق السقف يظنه Ekos مفتوحاً.
- **القيمة `"camera"`:** الكاميرا يجب أن **ترى** السقف مفتوحاً. أكثر أماناً، ويحتاج معايرة (الخطوة 9).

## 4) اختبار من Terminal (قبل Ekos)

```bash
python3 ~/roof/roof_calibrate.py esp-state    # قراءة فقط
python3 ~/roof/roof_calibrate.py esp-open     # يسألك أولاً: اكتب yes
python3 ~/roof/roof_calibrate.py esp-stop
python3 ~/roof/roof_calibrate.py esp-close
```
الحالة المطبوعة بعد الأمر مباشرة قد تكون قديمة بثانيتين، فهذا طبيعي.

## 5) إعداد Dome Scripting Gateway

1. في **Profile Editor**: اختر **Dome Scripting Gateway** في خانة **Dome**، واحفظ وشغّل البروفايل.
2. افتح **INDI Control Panel → Dome Scripting Gateway → Options**:
   - خانة **Folder:** اضغط ثلاث مرات على الخانة **اليمنى** لتحديد النص، واكتب `/home/stellarmate/roof/scripts`، ثم اضغط زر **Set** الكبير المقابل لقائمة السكربتات. تأكد أن **الخانة الوسطى** تغيّرت.
   - لا تغيّر أسماء السكربتات.
   - خانة **Type:** اختر Roll off
   - خانة **Mount Policy:** اختر Mount locks
   - من **Configuration** اضغط Save
3. أوقف البروفايل وشغّله من جديد، فبعض الخيارات لا تُطبَّق إلا بعد إعادة التشغيل.

## 6) إعداد التلسكوب (EQMod)

1. افتح **EQMod Mount → Options**:
   - خانة **Dome Policy:** اختر Dome locks
   - تأكد أن خانة **DOME** في Snoop devices = `Dome Scripting Gateway`
   - من **Configuration** اضغط Save
2. **وضع Park** (مرة واحدة، والتلسكوب في وضع الراحة):
   - من **Site Management → Park Options** اضغط **Current**، ثم **Write Data**.
   - ثم من **Main Control** اضغط **Park**. التلسكوب لن يتحرك، فقط تصير حالته Parked.

> **مهم:** لا تضغط Park قبل تسجيل الوضع الحالي، وإلا ذهب التلسكوب إلى وضع Park قديم وقد يصطدم بالسقف.

## 7) الترتيب الصحيح

- **فتح:** Unpark السقف ← انتظر حتى يكتمل ← Unpark التلسكوب.
- **إغلاق:** Park التلسكوب ← Park السقف.

| الرسالة | معناها |
|---|---|
| `Cannot Park Dome when mount is locking` | التلسكوب ليس Parked. اعمل Park له أولاً. هذه حماية Mount locks |
| التلسكوب يرفض Unpark | السقف مغلق. هذه حماية Dome locks |

استخدم **Park و Unpark** فقط، ولا تستخدم زري Open وClose في سطر Motion.

## 8) الـ Scheduler

في **Observatory Startup / Shutdown Procedure** مجموعات جاهزة تنفّذ الترتيب الصحيح تلقائياً:
- **البدء:** Unpark Dome → Unpark Mount
- **الإنهاء:** Park Mount → Park Dome

> قبل البدء، يتأكد الـ Scheduler أن **كل أجهزة البروفايل متصلة**. جهاز مفصول، كالفوكسر مثلاً، يوقفه برسالة `One or more INDI devices timed out`. وصّله أو احذفه من البروفايل.

## 9) الكاميرا (اختياري، الأكثر أماناً)

1. في `roof_config.py` ضع رابط RTSP للكاميرا في `CAMERA_RTSP`.
2. التقط صورة بشبكة المربعات:
   ```bash
   python3 ~/roof/roof_calibrate.py grab
   ```
   افتح `data/grid.jpg`، وعدّل `ROI` حتى يغطي ألواح السقف، و`CONTEXT_ROI` حتى يغطي جداراً ثابتاً.
3. والسقف مغلق:
   ```bash
   python3 ~/roof/roof_calibrate.py closed
   ```
4. اختبر مباشرة وأنت تفتح وتقفل:
   ```bash
   python3 ~/roof/roof_calibrate.py test
   ```
5. شغّل الخدمة واجعل الكاميرا هي المرجع:
   ```bash
   sudo systemctl start roof-monitor
   sed -i 's/^STATUS_SOURCE = .*/STATUS_SOURCE = "camera"/' ~/roof/roof_config.py
   ```

## 10) حل المشاكل

```bash
tail -20 ~/roof/data/roof.log                  # ماذا فعلت السكربتات
python3 ~/roof/roof_calibrate.py esp-state     # ماذا يقول الـ ESP
grep STATUS_SOURCE ~/roof/roof_config.py
```

| المشكلة | السبب والحل |
|---|---|
| `Timeout evaluating DOME_PARK.STATE` | Ekos لم يصله تأكيد الفتح. لو `STATUS_SOURCE = "camera"` والكاميرا غير معايرة، حوّله إلى `"esp"` |
| السقف فتح والتلسكوب لم يتحرك | نفس السبب السابق: Ekos ينتظر التأكيد |
| الـ ESP يقول `unknown` | أعاد التشغيل أو تحدّث. صحح الحالة من صفحته (الإعدادات) |
| `wrong ESP_USER / ESP_PASS` | كلمة السر في `roof_config.py` لا تطابق `secrets.yaml` |
| `ESP not reachable` | تأكد من `ESP_HOST`، وأن StellarMate والـ ESP على نفس الشبكة |

</div>
