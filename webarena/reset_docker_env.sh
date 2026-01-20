
# stop and remove the images
docker stop shopping_admin forum gitlab shopping
docker rm shopping_admin forum gitlab shopping
# start the images
docker run --name shopping --shm-size="2g" -p 7770:80 -d shopping_final_0712
docker run --name shopping_admin --shm-size="2g" -p 7780:80 -d shopping_admin_final_0719
docker run --name gitlab --shm-size="2g" -d -p 8023:8023 gitlab-populated-final-port8023 /opt/gitlab/embedded/bin/runsvdir-start
docker run --name forum --shm-size="2g" -p 9999:80 -d postmill-populated-exposed-withimg


docker start gitlab
docker start shopping
docker start shopping_admin
docker start forum
docker start kiwix33
cd /c2/taeil/AWM/openstreetmap-website
docker compose start