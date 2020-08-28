from typing import List

import pandas as pd
from SBTi.data.data_provider import DataProvider
from SBTi.interfaces import IDataProviderCompany, IDataProviderTarget


class CSVProvider(DataProvider):
    """
    Data provider skeleton for CSV files. This class serves primarily for testing purposes only!

    :param config: A dictionary containing a "path" field that leads to the path of the CSV file
    """

    def __init__(self, path: str, path_targets: str, encoding: str = "utf-8"):
        super().__init__()
        self.data = pd.read_csv(path, encoding=encoding)
        self.data_targets = pd.read_csv(path_targets, encoding=encoding)

    def get_targets(self, company_ids: list) -> List[IDataProviderTarget]:
        """
        Get all relevant targets for a list of company ids (ISIN). This method should return a list of
        IDataProviderTarget instances.

        :param company_ids: A list of company IDs (ISINs)
        :return: A list containing the targets
        """
        targets = self.data_targets.to_dict(orient="records")
        model_targets: List[IDataProviderTarget] = [IDataProviderTarget.parse_obj(target) for target in targets]
        model_targets = [target for target in model_targets if target.company_id in company_ids]
        return model_targets

    def get_company_data(self, company_ids: list) -> List[IDataProviderCompany]:
        """
        Get all relevant data for a list of company ids (ISIN). This method should return a list of IDataProviderCompany
        instances.

        :param company_ids: A list of company IDs (ISINs)
        :return: A list containing the company data
        """
        companies = self.data.to_dict(orient="records")
        model_companies: List[IDataProviderCompany] = [IDataProviderCompany.parse_obj(company) for company in companies]
        model_companies = [target for target in model_companies if target.company_id in company_ids]
        return model_companies

    def get_sbti_targets(self, companies: list) -> list:
        """
        For each of the companies, get the status of their target (Target set, Committed or No target) as it's known to
        the SBTi.

        :param companies: A list of companies. Each company should be a dict with a "company_name" and "company_id"
                            field.
        :return: The original list, enriched with a field called "sbti_target_status"
        """
        return self.data[
            (self.data["company_id"].isin([company["company_id"] for company in companies]) &
             self.data["company_id"].notnull())].copy()