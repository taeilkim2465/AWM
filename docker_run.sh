
echo "📦 GitLab 실행 중..."
# docker run -d --name gitlab -p 8023:8023 --restart always gitlab-populated-final-port8023:latest
docker run -d --name gitlab \
  -p 8023:8023 \
  --restart always \
  gitlab-populated-final-port8023:latest /assets/wrapper

echo "📦 Shopping 실행 중..."
docker run -d --name shopping -p 7770:7770 --restart always shopping_final_0712:latest

echo "📦 Shopping Admin 실행 중..."
# 내부 포트가 80인 경우가 많으므로 확인이 필요하지만, 일반적인 설정을 따릅니다.
docker run -d --name shopping_admin -p 7780:80 --restart always shopping_admin_final_0719:latest

echo "📦 Forum 실행 중..."
docker run -d --name forum -p 9999:80 --restart always postmill-populated-exposed-withimg:latest

echo "📦 Kiwix (Wikipedia) 실행 중..."
# docker run -d --name kiwix33 -p 8888:8080 --restart always ghcr.io/kiwix/kiwix-serve:3.3.0
docker run -d \
  --name kiwix33 \
  -p 8888:80 \
  -v /c2/taeil/AWM/wiki:/data \
  --restart always \
  ghcr.io/kiwix/kiwix-serve:3.3.0 \
  /data/wikipedia_en_all_maxi_2022-05.zim
