build:
	docker build -t cheezy-vpn-bot:latest .
run:
	docker run --env-file .env --restart=unless-stopped --mount type=bind,source=$(CURDIR)/db/db.sqlite3,target=/usr/src/app/db.sqlite3 -it -d --name cheezy-vpn-bot cheezy-vpn-bot
stop:
	docker stop cheezy-vpn-bot
attach:
	docker attach cheezy-vpn-bot
dell:
	docker rm cheezy-vpn-bot
run_it:
	docker run --env-file .env --restart=unless-stopped --mount type=bind,source=$(CURDIR)/db/db.sqlite3,target=/usr/src/app/db.sqlite3 -it --name cheezy-vpn-bot cheezy-vpn-bot
