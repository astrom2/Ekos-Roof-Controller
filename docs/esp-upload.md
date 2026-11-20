<div dir="rtl">

# رفع الكود على الـ ESP8266 (Wemos D1 mini)

الكود مكتوب بـ **ESPHome**: ملف `yaml` يتحول على كمبيوترك إلى برنامج (firmware)، ثم يُرفع للـ ESP. أول مرة يُرفع بكيبل USB، وبعدها عبر الواي فاي.

## 1) ما تحتاجه

- Wemos D1 mini، وكيبل USB **ينقل بيانات**. بعض كيبلات الشحن لا تنقل بيانات.
- كمبيوتر Mac أو Windows أو Linux، فيه **Python 3.10** أو أحدث.
- الواي فاي الذي سيتصل به الـ ESP في المرصد (2.4GHz).

## 2) تثبيت ESPHome

**Mac** (في Terminal):
```bash
python3 -m pip install --user esphome
esphome version
```
لو ظهر `command not found`، استخدم `python3 -m esphome` بدل `esphome` في كل الأوامر التالية.

**Windows:**
1. ثبّت Python من python.org، وضع علامة **Add Python to PATH** أثناء التثبيت.
2. افتح PowerShell واكتب:
   ```powershell
   pip install esphome
   esphome version
   ```

**Linux:**
```bash
pip3 install --user esphome
```

## 3) تنزيل المشروع

```bash
git clone https://github.com/<user>/ekos-roof-controller.git
cd ekos-roof-controller/esphome
```
أو نزّله من زر **Code ← Download ZIP**. المهم أن يكون داخل مجلد `esphome`:
```
esphome/
├── roof-controller.yaml
├── roof_pos.h            ← ضروري، بجانب الـ yaml
├── secrets.example.yaml
└── www/
    └── roof-ui.js        ← الصفحة العربية
```

## 4) ملف كلمات السر `secrets.yaml`

انسخ المثال:
```bash
cp secrets.example.yaml secrets.yaml
```
ثم افتحه وعدّل القيم:

| الحقل | معناه |
|---|---|
| `wifi_ssid` / `wifi_password` | شبكة الواي فاي في المرصد |
| `ap_password` | كلمة سر الشبكة الاحتياطية `Roof-Controller-Setup`، تظهر لو لم يجد الـ ESP الواي فاي. 8 أحرف على الأقل |
| `api_key` | مفتاح Home Assistant. أنشئه بالأمر `openssl rand -base64 32` |
| `ota_password` | كلمة سر التحديث عبر الشبكة |
| `web_user` / `web_password` | دخول الصفحة، وهي **نفسها** التي تكتبها في سكربتات Ekos |

> `secrets.yaml` لا يُرفع إلى GitHub (موجود في `.gitignore`)، فاحتفظ بنسخة منه.

## 5) ضبط مدة حركة سقفك

في أول `roof-controller.yaml`:
```yaml
substitutions:
  travel_s: "28.0"    # ثواني الحركة من مغلق إلى مفتوح بالكامل
```
قِس وقت سقفك بالساعة وعدّل الرقم. وغيّر نفس الرقم في `www/roof-ui.js` (`const TRAVEL = 28`).

## 6) الرفع الأول بالكيبل

1. وصّل الـ D1 mini بالكمبيوتر.
2. نفّذ:
   ```bash
   cd ekos-roof-controller/esphome
   esphome run roof-controller.yaml
   ```
3. أول مرة يستغرق البناء **5 إلى 10 دقائق**، لأنه ينزّل أدوات ESP8266. بعدها يصير أسرع.
4. يسألك عن طريقة الرفع، فاختر منفذ USB:
   - Mac: `/dev/cu.usbserial-xxxx` أو `/dev/cu.wchusbserial-xxxx`
   - Windows: `COM3` أو ما يشبهه
5. بعد الرفع تظهر سجلات الـ ESP. ابحث عن سطر مثل `IP Address: 192.168.100.115`. للخروج اضغط **Ctrl+C**، والـ ESP يبقى يعمل.

> **لا يظهر منفذ USB؟** الـ D1 mini يستخدم شريحة **CH340**. ثبّت تعريفها من موقع الشركة المصنعة (WCH)، وأعد توصيل الكيبل، وجرّب كيبلاً آخر.

## 7) ثبّت عنوان الـ ESP

في الراوتر، احجز للـ ESP **عنواناً ثابتاً** (DHCP reservation). سكربتات Ekos تستخدم هذا العنوان.

## 8) التحديثات بعد ذلك: عبر الواي فاي

نفس الأمر، والـ ESP لا يحتاج كيبل:
```bash
esphome run roof-controller.yaml
```
واختر الخيار الذي فيه العنوان، **OTA**. أو حدد العنوان مباشرة:
```bash
esphome run roof-controller.yaml --device 192.168.100.115
```

**أو من صفحة الـ ESP نفسها:**
1. ابنِ الملف بدون رفع:
   ```bash
   esphome compile roof-controller.yaml
   ```
2. الملف الجاهز في `.esphome/build/roof-controller/.pioenvs/roof-controller/firmware.bin`. المجلد مخفي، ففي Mac اضغط **Cmd + Shift + .** في Finder ليظهر.
3. في الصفحة: **الإعدادات ← تحديث البرنامج**، واختر `firmware.bin`.

> ارفع **firmware.bin** فقط. لو رفعت ملف الـ `yaml` يظهر `Update Failed`، والجهاز يبقى على البرنامج القديم بدون ضرر.

## 9) أول تشغيل

1. افتح `http://192.168.100.115` وادخل باسم المستخدم وكلمة السر.
2. الحالة تظهر **"غير معروف"**. من **الإعدادات**، اضغط **"السقف مغلق الآن"** أو **"السقف مفتوح الآن"** حسب الواقع. هذا لا يحرّك شيئاً.
3. جرّب وأنت عند السقف: **فتح** (اضغط مطولاً حتى يمتلئ الزر)، ثم **إيقاف** بعد ثوانٍ، ثم **إغلاق**.
4. لو قفل السقف لما ضغطت فتح، شغّل **"عكس الفتح والإغلاق"** في الإعدادات.
5. الريموت يعمل فقط بعد تفعيل مفتاح **ريموت 433MHz**.

## 10) مشاكل شائعة

| المشكلة | الحل |
|---|---|
| `No such file or directory` | لست داخل مجلد `esphome`. نفّذ `cd` إليه أولاً |
| `roof_pos.h: No such file` | الملف ناقص، ضعه بجانب `roof-controller.yaml` |
| `Update Failed` في الصفحة | رفعت ملف `.yaml` بدل `firmware.bin` |
| الحالة "غير معروف" | بعد التحديث الأول طبيعي. صححها من الإعدادات |
| الرسم لا يتحرك والأرقام متضاربة | الصفحة فقدت الاتصال، أعد تحميلها |
| الرفع عبر الشبكة لا يجد الجهاز | تأكد من العنوان، وأن الكمبيوتر على نفس الشبكة |
| الـ ESP يعيد التشغيل وحده | انظر **"آخر إعادة تشغيل"** في الإعدادات. غالباً ضعف تغذية 5V، فاستخدم مزوّداً أقوى |

</div>
