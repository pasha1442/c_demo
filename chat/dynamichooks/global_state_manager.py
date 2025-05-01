from datetime import datetime
import json
from typing import Dict, Any
from threading import Lock
import logging
from basics.utils import Singleton
from company.models import Company, CompanySetting

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class GlobalCompanyStateManager(metaclass=Singleton):
    def __init__(self):
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._state_ttl_minutes = 30

    def get_company_state(self, company_id: str) -> Dict[str, Any]:
        with self._lock:
            if company_id in self._state:
                last_updated = self._state[company_id].get('last_updated')
                if last_updated:
                    elapsed_minutes = (datetime.now() - last_updated).total_seconds() / 60
                    if elapsed_minutes > self._state_ttl_minutes:
                        try:
                            return self.fetch_and_cache_company_details(company_id)
                        except Exception as e:
                            logger.error(f"Error refreshing company state: {e}")
                return self._state[company_id]
            else:
                self._state[company_id] = {
                    "last_updated": datetime.now()
                }
                try:
                    return self.fetch_and_cache_company_details(company_id)
                except Exception as e:
                    logger.error(f"Error fetching company details: {e}")
                    return self._state[company_id]

    def update_company_state(self, company_id: str, key: str, value: Any):
        with self._lock:
            if company_id not in self._state:
                self.get_company_state(company_id)

            self._state[company_id][key] = value
            self._state[company_id]['last_updated'] = datetime.now()

    def fetch_and_cache_company_details(self, company_id: str):
        with self._lock:
            company = Company.objects.get(id=company_id)

            # Load webhook config from CompanySetting
            webhook_config = {}
            setting = CompanySetting.objects.filter(
                company=company,
                key=CompanySetting.KEY_CHOICE_SNOOPING_WEBHOOK_URLS
            ).first()
            if setting and isinstance(setting.value, dict):
                webhook_config = setting.value

            self._state[company_id] = {
                "name": company.name,
                "code": str(company.code),
                "webhook_config": webhook_config,
                "langfuse_keys": {
                    "secret_key": company.langfuse_secret_key,
                    "public_key": company.langfuse_public_key
                },
                "last_updated": datetime.now()
            }

            return self._state[company_id]
