[app]
title = Land Calculator
package.name = landcalculator
package.domain = org.zual
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = assets/*,images/*.png
source.file_extensions = py,png,jpg,kv
version = 1.0

requirements = python3,kivy,pillow,reportlab

orientation = portrait
fullscreen = 0
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 31
android.accept_sdk_license = True
icon.filename = 
presplash.filename = 

[buildozer]
log_level = 2
warn_on_root = 1
