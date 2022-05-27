# aim: The utilities of mysql operations
# author: zhangxunhui
# date: 2022-05-27

import pymysql


class MySQLUtils(object):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        autocommit: bool,
        dictcursor: bool,
    ):
        if (
            type(host) != str
            or type(port) != int
            or type(username) != str
            or type(password) != str
            or type(database) != str
        ):
            raise Exception(
                "MySQLUtils Error: host, port, username, password or database configuration wrong!"
            )
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.autocommit = autocommit
        self.conn = self.connect()
        if dictcursor:
            self.cur = self.conn.cursor(pymysql.cursors.DictCursor)
        else:
            self.cur = self.conn.cursor()

    def connect(self):
        db = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            database=self.database,
            autocommit=self.autocommit,
        )
        if db is None:
            raise Exception("MySQLUtils Error: cannot connect MySQL service!")
        return db

    def get_repo_id(self, ownername: str, reponame: str):
        self.cur.execute(
            "select id from repository where owner_name=%s and name=%s",
            (ownername, reponame),
        )
        repo_id = self.cur.fetchone()
        return repo_id
