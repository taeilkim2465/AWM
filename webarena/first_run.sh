#!/bin/bash

# 1. 환경 변수 설정
export SHOPPING="http://10.10.0.120:7770"
export SHOPPING_ADMIN="http://10.10.0.120:7780/admin"
export REDDIT="http://10.10.0.120:9999"
export GITLAB="http://10.10.0.120:8023"
export MAP="http://10.10.0.120:3000"
export WIKIPEDIA="http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export HOMEPAGE="http://10.10.0.120:4399"

echo "🚀 WebArena 컨테이너 생성을 시작합니다..."

# 2. 개별 서비스 컨테이너 생성 및 실행 (docker run)
# --restart always 옵션을 넣어두면 재부팅 시에도 자동으로 켜집니다.

echo "📦 GitLab 실행 중..."
docker run -d --name gitlab -p 8023:8023 --restart always gitlab-populated-final-port8023:latest

echo "📦 Shopping 실행 중..."
docker run -d --name shopping -p 7770:7770 --restart always shopping_final_0712:latest

echo "📦 Shopping Admin 실행 중..."
# 내부 포트가 80인 경우가 많으므로 확인이 필요하지만, 일반적인 설정을 따릅니다.
docker run -d --name shopping_admin -p 7780:80 --restart always shopping_admin_final_0719:latest

echo "📦 Forum 실행 중..."
docker run -d --name forum -p 9999:80 --restart always postmill-populated-exposed-withimg:latest

echo "📦 Kiwix (Wikipedia) 실행 중..."
docker run -d --name kiwix33 -p 8888:8080 --restart always ghcr.io/kiwix/kiwix-serve:3.3.0

# 3. OpenStreetMap 실행
echo "📦 OpenStreetMap 실행 중..."
if [ -d "/home/ubuntu/openstreetmap-website/" ]; then
    cd /home/ubuntu/openstreetmap-website/
    docker compose up -d
else
    echo "❌ 경고: /home/ubuntu/openstreetmap-website/ 디렉토리가 없습니다."
fi

echo "✅ 모든 서비스가 실행되었습니다. 'docker ps'로 상태를 확인하세요."
