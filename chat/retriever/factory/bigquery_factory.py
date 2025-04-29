from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError
import time
from company.models import CompanySetting

class BigQueryFactory:
    bigquery_client_instances = {}

    def __init__(self, company):
        start_time = time.time()
        if company:
            self.company = company
            self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_KB_BQ_CREDENTIALS, company=company)
        else:
            self.company = None
            self.credentials = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_KB_BQ_CREDENTIALS)

        self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}

        self.project_id = self.credentials_dict.get("project_id")
        self.credentials_path = self.credentials_dict.get("credentials_path")

        # Initialize the BigQuery client
        self.client = bigquery.Client.from_service_account_json(self.credentials_path, project=self.project_id)

    @classmethod
    def get_bigquery_instance(cls, company):
        if company.name in cls.bigquery_client_instances:
            return cls.bigquery_client_instances[company.name]
        else:
            obj = cls(company)
            cls.bigquery_client_instances[company.name] = obj
            return obj

    def query_database(self, query):
        """
        Executes a BigQuery SQL query and returns the results.
        """
        try:
            query_job = self.client.query(query)
            result = query_job.result()  # Waits for the query to finish
            rows = [dict(row.items()) for row in result]
            return rows
        except GoogleAPICallError as e:
            raise Exception(f"BigQuery query failed: {e}")

