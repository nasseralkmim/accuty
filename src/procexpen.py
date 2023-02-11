import re
import sys
from pypdf import PdfReader
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

reader = PdfReader(sys.argv[1])
text = ""
HEADER_LINES = 6  # name, address, iban, date, nr, header
FOOTER_LINES = 2  # time frame, description, empty
IGNORE_LAST_PAGES = 2
CATEGORIES_TO_ADJUST = ["Income", "Direct Debits", "Outgoing Transfers"]
expenses_list = []

for page in reader.pages[:-IGNORE_LAST_PAGES]:
    text = page.extract_text()
    # split each line ignore header and footer
    lines = text.split("\n")[HEADER_LINES:-FOOTER_LINES]

    index = 0
    not_end = True
    while not_end is True:
        description = lines[index]
        category = lines[index + 1]

        # adjust index when "income" or "direct debt" by skipping some information
        if category in CATEGORIES_TO_ADJUST:
            skip = 2  # skip iban+bic and message
            valuedate = lines[index + 2 + skip]
            index += skip
        else:
            valuedate = lines[index + 2]

        # check if at last row of page before updating the index
        if lines[index + 2] == lines[-1]:
            not_end = False

        index += 3

        row = pd.DataFrame(
            {
                "description": [description],
                "category": [category],
                "valuedate": [valuedate],
            }
        )
        expenses_list.append(row)


# stack the rows into single dataframe
expenses = pd.concat(expenses_list, axis=0, ignore_index=True)

# split the value and date into different columns
expenses[["date", "value"]] = expenses.valuedate.str.split(expand=True).iloc[:, 2:4]
# remove the old column
expenses = expenses.drop("valuedate", axis="columns")

# process value
expenses.value = (
    expenses.value.str.split("€", expand=True)
    .iloc[:, 0]
    .str.replace(".", "", regex=False)       # +2.139,86 -> +2139,86
    .str.replace(",", ".")      # +2139,86
    .astype(float)
    * -1                        # positive is expense, negative income (opposite from statement)
)

# process date
expenses.date = expenses.date.str.extract(r"(\d{2}.\d{2}.\d{4})", expand=True).iloc[:, 0]
expenses.date = pd.to_datetime(expenses.date, format="%d.%m.%Y").dt.strftime("%d/%b/%y")

# process categories
expenses.category = expenses.category.str.split("•", expand=True).iloc[:, -1]
expenses.category = expenses.category.str.replace("Bars & Restaurants", "restaurant")
expenses.category = expenses.category.str.replace("Groceries", "food")
expenses.category = expenses.category.str.replace("Transport", "other")
expenses.category = expenses.category.str.replace("Miscellaneous", "other")
expenses.category = expenses.category.str.replace("Shopping", "shopping")
expenses.category = expenses.category.str.replace("Leisure", "shopping")
expenses.category = expenses.category.str.replace("Healthcare", "shopping")

# adjust order
expenses = expenses[["date", "category", "value", "description"]]
expenses = expenses.sort_values(by="date", ascending=False)

expenses.to_csv(sys.argv[1][:-3]+"csv", sep="\t", index=False)
