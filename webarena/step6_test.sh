HOSTNAME="10.10.0.120"
curl -s -o /dev/null -w "Shopping (7770): %{http_code}\n" http://$HOSTNAME:7770
curl -s -o /dev/null -w "Shopping Admin (7780): %{http_code}\n" http://$HOSTNAME:7780
curl -s -o /dev/null -w "Forum (9999): %{http_code}\n" http://$HOSTNAME:9999
curl -s -o /dev/null -w "Wikipedia (8888): %{http_code}\n" http://$HOSTNAME:8888
curl -s -o /dev/null -w "Map (3000): %{http_code}\n" http://$HOSTNAME:3000
curl -s -o /dev/null -w "GitLab (8023): %{http_code}\n" http://$HOSTNAME:8023
curl -s -o /dev/null -w "Map tile: %{http_code}\n" http://$HOSTNAME:3000/tile/0/0/0.png