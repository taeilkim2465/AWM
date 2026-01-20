#!/bin/bash

# 모든 관련 컨테이너를 중지합니다.
echo "🛑 Stopping all WebArena containers..."
docker stop shopping_admin forum gitlab shopping kiwix33
if [ -d "/c2/taeil/AWM/openstreetmap-website/" ]; then
    cd /c2/taeil/AWM/openstreetmap-website/
    docker compose stop
    cd - > /dev/null
fi

# 재생성할 컨테이너만 삭제합니다.
echo "🗑️ Removing containers to be re-created..."
docker rm shopping_admin forum gitlab shopping

# --shm-size와 함께 컨테이너를 다시 생성하고 시작합니다.
echo "🚀 Re-creating and starting main services..."
docker run -d --name shopping -p 7770:80 --shm-size="2g" --restart always shopping_final_0712
docker run -d --name shopping_admin -p 7780:80 --shm-size="2g" --restart always shopping_admin_final_0719
docker run -d --name gitlab -p 8023:8023 --shm-size="2g" --restart always gitlab-populated-final-port8023 /assets/wrapper
docker run -d --name forum -p 9999:80 --shm-size="2g" --restart always postmill-populated-exposed-withimg

# 삭제하지 않은 서비스를 다시 시작합니다.
echo "🚀 Restarting persistent services..."
docker start kiwix33
if [ -d "/c2/taeil/AWM/openstreetmap-website/" ]; then
    cd /c2/taeil/AWM/openstreetmap-website/
    docker compose up -d
    cd - > /dev/null
fi

echo "✅ All services have been restarted."
