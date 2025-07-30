import pandas as pd
import os

df = pd.read_excel('C:/Users/HP/Downloads/EV업데이트 0729 1846.xlsx')

except_list = ['승인불가', '신청포기', '지원취소']

df = df[~df['신청단계'].isin(except_list)]

print(df.head())




