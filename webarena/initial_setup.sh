export SHOPPING="http://10.10.0.120:7770"
export SHOPPING_ADMIN="http://10.10.0.120:7780/admin"
export REDDIT="http://10.10.0.120:9999"
export GITLAB="http://10.10.0.120:8023"
export MAP="http://10.10.0.120:3000"
export WIKIPEDIA="http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export HOMEPAGE="http://10.10.0.120:4399"

# python config_files/generate_test_data.py

docker start gitlab
docker start shopping
docker start shopping_admin
docker start forum
docker start kiwix33
cd /c2/taeil/AWM/openstreetmap-website
docker compose start