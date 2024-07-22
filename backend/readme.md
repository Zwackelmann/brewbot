### Setup CAN Interface
```
sudo ip link set can0 type can bitrate 125000
sudo ip link set up can0
```

### Run backend
```
uvicorn brewbot.rest.api:app --reload
```

### Setup nginx server

Create file `/etc/nginx/sites-available/brewbot.conf`
```
server {
    listen 8080;

    server_name localhost;

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://localhost:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Link config to `sites-enabled`
```
sudo ln -s /etc/nginx/sites-available/your-site.conf /etc/nginx/sites-enabled/
```