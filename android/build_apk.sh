#!/bin/sh
# Builds android/MH3U-Quest-Notebook.apk (developer tool, Linux or macOS).
#
# Needs: Java (with jarsigner), Python 3 with the 'cryptography' and 'repro-apk' packages,
# and apktool (https://apktool.org, one .jar). No Android SDK: the app is the page in web/
# shown in a WebView, its small native part is written in smali (native/smali) and apktool
# assembles it. The APK is signed v1 (jarsigner) and v2 (tools/sign_apk.py).
#
#   APKTOOL=/path/to/apktool.jar KEYSTORE=/path/to/key.p12 KEYPASS=... android/build_apk.sh
#
# Keep the keystore safe and private: Android only updates the app with an APK signed by the
# same key. Make one with:
#   keytool -genkeypair -storetype PKCS12 -keystore key.p12 -alias notebook -keyalg RSA -keysize 3072 -validity 12000
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
: "${APKTOOL:?set APKTOOL to apktool.jar}" "${KEYSTORE:?set KEYSTORE}" "${KEYPASS:?set KEYPASS}"
WORK=$(mktemp -d)
mkdir -p "$WORK/app"
cp -r "$HERE/native/." "$WORK/app/"
mkdir -p "$WORK/app/assets/img/maps"
cp "$HERE/web/index.html" "$HERE/web/app.js" "$HERE/web/style.css" "$HERE/web/data.js" "$WORK/app/assets/"
cp "$ROOT/assets/items.png" "$ROOT/assets/monsters_54.png" "$WORK/app/assets/img/"
cp "$ROOT"/assets/maps/map*_160.png "$WORK/app/assets/img/maps/"
java -jar "$APKTOOL" b "$WORK/app" -o "$WORK/unsigned.apk"
jarsigner -keystore "$KEYSTORE" -storetype PKCS12 -storepass "$KEYPASS" -sigalg SHA256withRSA -digestalg SHA-256 \
  -sigfile CERT "$WORK/unsigned.apk" notebook
repro-apk zipalign --pad-like-apksigner "$WORK/unsigned.apk" "$WORK/aligned.apk"
python3 "$HERE/tools/sign_apk.py" "$KEYSTORE" "$KEYPASS" "$WORK/aligned.apk" "$HERE/MH3U-Quest-Notebook.apk"
echo "Built $HERE/MH3U-Quest-Notebook.apk"
