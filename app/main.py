from checks.structure import structure_check
from app.loader import load_data

df=load_data("C:\\Users\\user\\Downloads\\bestsellers-with-categories.xlsx")
structure_info = structure_check(df)
print(structure_info)