import mysql.connector
from mysql.connector import Error
import time
from company.models import Company, CompanyCustomer, CompanyEntity, CompanyPostProcessing, CompanySetting

class MySQLFactory:
    mysql_connection_instances = {}


    def __init__(self, company):
        start_time = time.time()
        if company:
            self.company = company
            self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_KB_SQL_CREDENTIALS, company=company)
        else:
            self.company = None
            self.credentials = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_KB_SQL_CREDENTIALS)

        self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}

        self.mysql_username = self.credentials_dict.get("mysql_username")
        self.mysql_password = self.credentials_dict.get("mysql_password")
        self.mysql_host = self.credentials_dict.get("mysql_host")
        self.mysql_database = self.credentials_dict.get("mysql_database")
        self.mysql_port = self.credentials_dict.get("mysql_port", 3306)

        self.connection = mysql.connector.connect(
            host=self.mysql_host,
            user=self.mysql_username,
            password=self.mysql_password,
            database=self.mysql_database,
            port=self.mysql_port
        )

    @classmethod
    def get_mysql_instance(cls, company):
        if company.name in cls.mysql_connection_instances and cls.mysql_connection_instances[company.name].connection.is_connected():
            return cls.mysql_connection_instances[company.name]
        else:
            obj = cls(company)
            cls.mysql_connection_instances[company.name] = obj
            return obj

    def query_database(self, mysql_query):
        cursor = self.connection.cursor()
        cursor.execute(mysql_query)
        result = cursor.fetchall()
        cursor.close()
        columns = [desc[0] for desc in cursor.description]
        result.insert(0, columns)  # Insert column names as the first row
        return result



