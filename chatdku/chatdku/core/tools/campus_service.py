import pandas as pd


class CampusService_tool:

    def __init__(self, file_path) -> None:
        self.file_path = file_path

    def query(self, search_string):

        df = pd.read_excel(self.file_path)

        keys = df.iloc[0, [0, 4, 5, 6, 7]].tolist()

        search_string_lower = search_string.lower()
        df_lower = df.applymap(lambda x: str(x).lower() if pd.notna(x) else "")

        match = df_lower[df_lower[0] == search_string_lower]
        if not match.empty:
            values = match.iloc[0, [0, 4, 5, 6, 7]].tolist()
            return {key: value for key, value in zip(keys, values) if value}

        match = df_lower[df_lower[2] == search_string_lower]
        if not match.empty:
            values = match.iloc[0, [0, 4, 5, 6, 7]].tolist()
            return {key: value for key, value in zip(keys, values) if value}

        match = df_lower[df_lower[3] == search_string_lower]
        if not match.empty:
            values = match.iloc[0, [0, 4, 5, 6, 7]].tolist()
            return {key: value for key, value in zip(keys, values) if value}

        contains = df_lower[df_lower[1].str.contains(search_string_lower, na=False)]
        if not contains.empty:
            values = contains.iloc[0, [0, 4, 5, 6, 7]].tolist()
            return {key: value for key, value in zip(keys, values) if value}

        return "No Info Found"
