#!/bin/bash

# ==========================================
# [설정] 본인의 서버 IP 또는 도메인으로 변경하세요
# 로컬에서 실행 중이라면 'localhost' 또는 '127.0.0.1'
# ==========================================
HOSTNAME="localhost" 

echo ">>> [1/5] 환경 초기화 (기존 컨테이너 삭제 및 이미지 실행)..."
# 1. 기존 컨테이너 중지 및 삭제
docker stop shopping_admin forum gitlab shopping 2>/dev/null
docker remove shopping_admin forum gitlab shopping 2>/dev/null

# 2. 컨테이너 실행 (백그라운드)
docker run --name shopping -p 7770:80 -d shopping_final_0712
docker run --name shopping_admin -p 7780:80 -d shopping_admin_final_0719
docker run --name forum -p 9999:80 -d postmill-populated-exposed-withimg
# GitLab 실행 (가장 오래 걸리므로 먼저 띄우고 다른 작업 진행)
docker run --name gitlab -d -p 8023:8023 gitlab-populated-final-port8023 /opt/gitlab/embedded/bin/runsvdir-start

echo ">>> [2/5] GitLab 부팅 대기 중... (그 동안 쇼핑몰 설정을 진행합니다)"
# GitLab이 켜지는 동안 쇼핑몰 설정을 먼저 해서 시간을 아낍니다.
sleep 30 

echo ">>> [3/5] 쇼핑몰 및 포럼 설정 적용..."

# Shopping 설정
docker exec shopping /var/www/magento2/bin/magento setup:store-config:set --base-url="http://$HOSTNAME:7770"
docker exec shopping mysql -u magentouser -pMyPassword magentodb -e "UPDATE core_config_data SET value='http://$HOSTNAME:7770/' WHERE path = 'web/secure/base_url';"
docker exec shopping /var/www/magento2/bin/magento cache:flush

# Shopping Admin 설정
docker exec shopping_admin php /var/www/magento2/bin/magento config:set admin/security/password_is_forced 0
docker exec shopping_admin php /var/www/magento2/bin/magento config:set admin/security/password_lifetime 0
docker exec shopping_admin /var/www/magento2/bin/magento setup:store-config:set --base-url="http://$HOSTNAME:7780"
docker exec shopping_admin mysql -u magentouser -pMyPassword magentodb -e "UPDATE core_config_data SET value='http://$HOSTNAME:7780/' WHERE path = 'web/secure/base_url';"
docker exec shopping_admin /var/www/magento2/bin/magento cache:flush

echo ">>> [4/5] GitLab 긴급 조치 (DB Lock 해제 및 복구)..."
# 요청하신 코드를 여기에 통합하여, reconfigure 전에 문제를 해결합니다.
echo "    - Removing postmaster.pid..."
docker exec gitlab rm -f /var/opt/gitlab/postgresql/data/postmaster.pid
echo "    - Resetting WAL logs..."
docker exec -u gitlab-psql gitlab /opt/gitlab/embedded/bin/pg_resetwal -f /var/opt/gitlab/postgresql/data
echo "    - Restarting GitLab services..."
docker exec gitlab gitlab-ctl restart

# 서비스 재시작 후 안정화 대기 (매우 중요)
echo ">>> GitLab 재시작 후 안정화 대기 (약 2분)..."
sleep 120

echo ">>> [5/5] GitLab 최종 구성 (Reconfigure)..."
# 권한 업데이트 및 URL 설정
docker exec gitlab update-permissions
docker exec gitlab sed -i "s|^external_url.*|external_url 'http://$HOSTNAME:8023'|" /etc/gitlab/gitlab.rb

# 대망의 Reconfigure (이제 멈추지 않을 것입니다)
docker exec gitlab gitlab-ctl reconfigure

echo "=========================================="
echo " 모든 설정이 완료되었습니다!"
echo " GitLab 접속: http://$HOSTNAME:8023"
echo "=========================================="