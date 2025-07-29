build:
	docker build -t steambot:latest .
run:
	docker run --env-file .env --restart=unless-stopped --mount type=bind,source=$(CURDIR)/db/db.sqlite3,target=/usr/src/app/db.sqlite3 -it -d --name steambot steambot
stop:
	docker stop steambot
attach:
	docker attach steambot
dell:
	docker rm steambot