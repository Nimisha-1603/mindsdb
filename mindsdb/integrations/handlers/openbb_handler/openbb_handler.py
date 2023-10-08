import pandas as pd
from typing import Dict

from openbb import obb

from mindsdb.integrations.handlers.openbb_handler.openbb_tables import OpenBBtable
from mindsdb.integrations.libs.api_handler import APIHandler
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
)
from mindsdb.utilities import log
from mindsdb_sql import parse_sql


class OpenBBHandler(APIHandler):
    """A class for handling connections and interactions with the OpenBB Platform.

    Attributes:
        PAT (str): OpenBB's personal access token. Sign up here: https://my.openbb.co
        is_connected (bool): Whether or not the user is connected to their OpenBB account.

    """

    def __init__(self, name: str = None, **kwargs):
        """Registers all API tables and prepares the handler for an API connection.

        Args:
            name: (str): The handler name to use
        """
        super().__init__(name)
        self.PAT = None

        args = kwargs.get("connection_data", {})
        if "PAT" in args:
            self.PAT = args["PAT"]

        self.is_connected = False

        self._register_table("openbb_fetcher", OpenBBtable(self))

    def connect(self) -> bool:
        """Connects with OpenBB account through personal access token (PAT).

        Returns none.
        """
        self.is_connected = False
        obb.account.login(pat=self.PAT)

        # Check if PAT utilized is valid
        if obb.user.profile.active:
            self.is_connected = True
            return True

        return False

    def check_connection(self) -> StatusResponse:
        """Checks connection to OpenBB accounting by checking the validity of the PAT.

        Returns StatusResponse indicating whether or not the handler is connected.
        """

        response = StatusResponse(False)

        try:
            if self.connect():
                response.success = True

        except Exception as e:
            log.logger.error(f"Error connecting to OpenBB Platform: {e}!")
            response.error_message = e

        self.is_connected = response.success
        return response

    def _process_cols_names(self, cols: list) -> list:
        new_cols = []
        for element in cols:
            # If the element is a tuple, we want to merge the elements together
            if type(element) == tuple:
                # Ensure that there's more than one element in the tuple
                if len(element) > 1:
                    new_cols.append("_".join(map(str, element)))
                else:
                    new_cols.append(element[0])
            else:
                new_cols.append(element)
        return new_cols

    def _openbb_fetcher(self, params: Dict = None) -> pd.DataFrame:
        """Gets aggregate trade data for a symbol based on given parameters

        Returns results as a pandas DataFrame.

        Args:
            params (Dict): Trade data params (symbol, interval, limit, start_time, end_time)
        """
        self.connect()

        try:
            if params is None:
                log.logger.error("At least cmd needs to be added!")
                return pd.DataFrame()

            # get the OpenBB command to get the data from
            cmd = params.pop("cmd")

            args = ""
            # if there are parameters create arguments as a string
            if params:
                for arg, val in params.items():
                    args += f"{arg}={val},"

                # remove the additional ',' added
                if args:
                    args = args[:-1]

            # recreate the OpenBB command with the arguments
            openbb_cmd = f"{cmd}({args})"

            OBBject = eval(openbb_cmd)

            data = OBBject.to_df()
            data.reset_index(inplace=True)

            # MindsDB doesn't handle well '-' in column names
            data.columns = self._process_cols_names(data.columns)

            print(data.columns)

        except Exception as e:
            log.logger.error(f"Error accessing data from OpenBB: {e}!")
            data = pd.DataFrame()

        return data

    def native_query(self, query: str = None) -> Response:
        ast = parse_sql(query, dialect="mindsdb")
        return self.query(ast)

    def call_openbb_api(
        self, method_name: str = None, params: Dict = None
    ) -> pd.DataFrame:
        """Calls the OpenBB Platform method with the given params.

        Returns results as a pandas DataFrame.

        Args:
            method_name (str): Method name to call (e.g. klines)
            params (Dict): Params to pass to the API call
        """
        if method_name == "openbb_fetcher":
            return self._openbb_fetcher(params)
        raise NotImplementedError(
            "Method name {} not supported by OpenBB Platform Handler".format(
                method_name
            )
        )
