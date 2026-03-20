Chaquopy: локальные колёса (.whl)
================================

Сюда кладите скачанные вручную Android-колёса с https://chaquo.com/pypi-13.1/

Для NumPy под текущий проект (Python 3.8 / cp38) и ABI из build.gradle.kts:

  - numpy-1.19.5-0-cp38-cp38-android_21_arm64_v8a.whl       (телефон arm64)
  - numpy-1.19.5-0-cp38-cp38-android_16_armeabi_v7a.whl    (arm 32-bit)
  - numpy-1.19.5-0-cp38-cp38-android_21_x86_64.whl         (эмулятор x86_64)

Файлы .whl в git не коммитятся (см. корневой .gitignore).

После копирования снова запустите: gradlew installDebug
