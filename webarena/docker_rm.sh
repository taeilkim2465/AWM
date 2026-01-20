echo "🛑 WebArena 컨테이너를 정지하고 삭제합니다..."

# 1. 개별 서비스 정지 및 삭제
# 컨테이너 이름을 지정하여 삭제합니다.
docker stop gitlab shopping shopping_admin forum kiwix33
docker rm gitlab shopping shopping_admin forum kiwix33

# 2. OpenStreetMap (Docker Compose) 정리
if [ -d "/home/ubuntu/openstreetmap-website/" ]; then
    echo "🗺️ OpenStreetMap 정리 중..."
    cd /home/ubuntu/openstreetmap-website/
    # down 명령어는 컨테이너를 정지하고 동시에 삭제합니다.
    docker compose down
else
    echo "❌ 경고: /home/ubuntu/openstreetmap-website/ 디렉토리가 없습니다."
fi

echo "✅ 모든 컨테이너가 성공적으로 제거되었습니다."