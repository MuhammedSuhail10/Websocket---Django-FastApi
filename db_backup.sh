#!/bin/bash

# Variables
CONTAINER_NAME="carrom_mysql_db"
DB_USER="bagheera_admin"
DB_NAME="bagheera_carrom_db"
BACKUP_DIR="/home/ubuntu/db_backups"
DATE=$(date +'%Y-%m-%d_%H-%M-%S')

# Make sure backup directory exists
mkdir -p $BACKUP_DIR

# Run backup
docker exec -t $CONTAINER_NAME mysqldump -u $DB_USER -p"$(docker exec $CONTAINER_NAME printenv MYSQL_PASSWORD)" $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# Optional: keep only last 7 backups
ls -1tr $BACKUP_DIR/db_backup_*.sql | head -n -7 | xargs -d '\n' rm -f --