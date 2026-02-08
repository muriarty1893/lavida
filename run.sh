#!/bin/bash

# 1. Masaüstü arayüzünün kendine gelmesi için 10 saniye bekle
sleep 10

# 3. Sanal ortamı aktif et
source main_env/bin/activate

# 2. Klasöre git
cd /home/murat/Desktop/lavida


# 4. Uygulamayı başlat ve tüm çıktıları log dosyasına yaz
# (Hata olursa bu dosyanın içine bakacağız)
python main.py > startup_log.txt 2>&1