import datetime

COUPANG_COOKIES = [
    {"name": "_abck", "value": "C722C8F883B5ACB82244C0B4D01E9931~0~YAAQDtojF7EbP3yXAQAAnxy/hg59drRKUw5+hSOLXuaeCtG271Ptw5Bn6TRofzvKvOG7T494n8xDrlKmz67RVVyhPWrdBvtotJfm3XPyad4OKazUOFDfkfdnpddvPU5+mouEdAOfrGbrraaxUeOie+Od/1Yd5SIxr4hbye9VDc0W1qvAEMO7PKgaPpKkF0YHXj1iNIJleR5c2+vNspPoTGKVeatAlHG/85rjNrt1UhIdXkdp+HCjUSidjoYXPTQfv8t8q2CUyIBd/rmykj66FR8r7UJK8Q1Yqz+09EPhQiabGc3J2i9zo6RiXJgTH9cL2jqDRiHh9o5LfmR25yF7+7e67uiaFsdQw80zOO5pAVoyYOZFh5tJb23w/EOED7h82tQodbdBrfGy6n5P/EiXaThZu0ezlJ4ct1M9vd3dupMsG4T9hFRGEEsApeCY86Ka0yyvja3zvq/VFCpv/dHxbu1geBIMiOg9RrW9kShDzIc+jGQAVbLPovppeNwUcE5TOj9tLiRmf4AgLoi7uvGppLkE870S7w+wHor2jlkFTiql+UzuoKKkgjYseb7s/FQ80gejzkSTi5hiULHflAlSuerZ5iAAwXVPAGvXx76r82uNDAt7mTvixUDNJbRpz/o=~-1~||0||~-1", "path": "/", "expiry": 1781857961},
    {"name": "_fbp", "value": "fb.1.1750311141345.554637432554019344", "path": "/", "expiry": 1758097482},
    {"name": "ak_bmsc", "value": "6A3281A2776075873632E18F4A00B394~000000000000000000000000000000~YAAQpkg7F6hfpXiXAQAAa5i3hhzPO3f2ATv7RJ1bNPwEEPT7Pp/VTNrd8kPcCOWczpiW376WRmrVwCgsnm7I0+cet6NjP5xcMOLsaj+TaF/Uok9BdKFBhps5JoBhnGQl3mBHMQfNBp0HRCyLu2/LGHAGKFpRoSWn3fOyjYwWDDoLxqK56Mf9X972zmNoqSY2SkdE1QP83fLbGS1y47LuciHI2IlpxKRz0xaDPUYKsZYXNhcyz5/CvERbXZCzFljzC9nZh+OsKuHQF0Xj5EUQ2JXq5vm0Ceh8I82GmxpfykwFO+Cw2S9+mQETi4+4kKA6kJZ+s10rCceiYmaJx6toRc29YdJeYFZpvLSOu1Nn8UfhCftHYgRs7PHZ5Hb9S9a7wekTBLu+M6qFbcgXAL7o8M7WmScKcaT4aqvi516Wp4xARKQ6tX09ezpIxc1W/QUvC8Q3xLEcUkhyGjWknhLSosZqtCLR", "path": "/", "expiry": 1755627140},
    {"name": "baby-isWide", "value": "wide", "path": "/", "expiry": 1755700854},
    {"name": "bm_lso", "value": "E6EE6D1517178388ED617DED4C02B1D225FE9E786906C95A4A0F630FBE271F40~YAAQpkg7F6tfpXiXAQAAa5i3hgTLNebW+vwoJt5nteZGqkvgrFKyOvX901ph28RlTPG7iU9FM0N8ZUoJx+dQszMe9Ck/XGqXgmMudv1BtuCm4FHtnCTzE2+K4Mr9BNDPe8dQ7a6TzAefd7H420Qs703o/G1te/vYBQXyWVh6dmqTS5uncuR922fji91b7adEUq3UgdTnbaYnoYMaZ4y/OzHf5F8oXxaHNxChL6USYoALZt8fIgwqF1oBixbuPi6ej7l5WY9257SSjQlYWqyaY1WcEnBfG49hP68euijwB2o+PI+It9o+Y1/wnW9CmMXvLnopCEPy8UCW0SSHYxo5p+Zr775j60xFo+5NS92XWQcKFl4kMXpjjg1/xfPJGNDWtktAWRLDZMlvZyT6mHrY5fTSIOlnPDZb4MyWXsSu0J0+lC7SjugKtiHOMdHlsgnF5gitXInqYBWSvNbTUdaN/98=^1750311868681", "path": "/", "expiry": 1758216268},
    {"name": "bm_s", "value": "YAAQpkg7FyNopXiXAQAAvdC3hgM3tHMuEf+fppoYziyXKAGpkP25U3i4A1CgjVcPqNWg4e4DNyvXyVR6V4zS92+DtrrZRzF2OKFKgra0bMJv8psDbLEQQSRHfaLHhGeO40tqeQWP7jca4+n0h63242mkLSL1tZo9yY59ZT92/lgxOhWFOdDVbWs3gDHBO96qeXz5KtP9veU5fpiaQzEYDRjB0s8l0A6SE+tsY9Xn+onu/qSiKMCfZmRbYcY/OZnTgCC9y2q4YpxCaW4+Jd49gfFXSTY4Ig4bugtn7cTd+FTIlAEdGoROdFeumB912YBpT+gOhhiWFYtOVju0RKQS8eCRSXbZxPJRNO46rJljHuDX7uxcqMxE1BfSzuWCO2tGTb4jlQBnQzkm5n2x9kPeV7egUNU4KzfXStfzGPOolrrN+M8fL4EF7XCSH76JUma5Uycj4CCfhM7wVbOsy4SJg172YmqHUGd6+5KgpvHQ1AnUwiSfo3b9OjuJfkc74G6Cq0iCLuYBaE+YQtBZYr241aayRfsLHRPdAKvTv1ATJ9Vj3orKoMPuKqH0+z0GD3EmVZ1ZXBif59aZ43Wbs59N6Q==", "path": "/", "expiry": 1758293082},
    {"name": "bm_sc", "value": "4~1~819135024~YAAQpkg7F5pgpXiXAQAAI5+3hgT9qiLe8Mb96yqM+dP0D/DKkeQyMHUVTRk/f5H84UKo49MtRE9xS4XWvNd/GaYdS6ckIe7Lo+faPL/Hy1RvTGUeaSLuksO1JLgn/I20qwn+oXqyrXNpUCaCQ9EJfRYJN0nwmkv77NnQHxvlfIvHmW5yHjOVptDUUSu9jHgEC5f34lEq7NZlQDm3QhM6aLHffhCec0qyzGvnjFkErkVEvN00kuoIZC8vTQ7kOfaB8ABFpLqnQzjMoTgxUntJl0R4SUAH3mU+TWC/uIXZ7hSaf7gj84SLuAmloYcQA05IjaN3EoLIDUxI7qzSniPz422PGay/EoHONG3flXpl8fM2ncxVajyztHcZhC1P8278xqDgS96SYu0wcWEFlUMfLKTAhfOoAgN3cn5XZPfcsAl8Hd2vy1KX2BuK35GMCr9ViP9QYb1bweNDqFgTWKGi3QsvQ5fZV/+tVzdfrmXcgLuARYGiTT3njlH7Nz7aXEzKAseyoq8rXtxXMUYLA8Ptd6S/u/Z7fYFFkpYNr8p/2cOFmXvm7mlCV/ZulBJjzuIg0O0m59lRZEBDt8oYilMlDqL5Y/2AFkTk3yjfH+2tO0zQDOggFFPnxJfcZgw8or2ql3jw", "path": "/", "expiry": 1755627329},
    {"name": "bm_so", "value": "E6EE6D1517178388ED617DED4C02B1D225FE9E786906C95A4A0F630FBE271F40~YAAQpkg7F6tfpXiXAQAAa5i3hgTLNebW+vwoJt5nteZGqkvgrFKyOvX901ph28RlTPG7iU9FM0N8ZUoJx+dQszMe9Ck/XGqXgmMudv1BtuCm4FHtnCTzE2+K4Mr9BNDPe8dQ7a6TzAefd7H420Qs703o/G1te/vYBQXyWVh6dmqTS5uncuR922fji91b7adEUq3UgdTnbaYnoYMaZ4y/OzHf5F8oXxaHNxChL6USYoALZt8fIgwqF1oBixbuPi6ej7l5WY9257SSjQlYWqyaY1WcEnBfG49hP68euijwB2o+PI+It9o+Y1/wnW9CmMXvLnopCEPy8UCW0SSHYxo5p+Zr775j60xFo+5NS92XWQcKFl4kMXpjjg1/xfPJGNDWtktAWRLDZMlvZyT6mHrY5fTSIOlnPDZb4MyWXsSu0J0+lC7SjugKtiHOMdHlsgnF5gitXInqYBWSvNbTUdaN/98=", "path": "/", "expiry": 1755701068},
    {"name": "bm_ss", "value": "ab8e18ef4e", "path": "/", "expiry": 1755628340},
    {"name": "bm_sv", "value": "BFAE5765DB8C1217F08121DC0E765CBC~YAAQpkg7FyRopXiXAQAAvdC3hhxqTQwM2pxQ3LoAwtwm236S4+YjxvgV9K0sf7HAHs3mV2ZdUVKMNBV5nIM17cRpGu3lKENFMYQBx18mCT96AlJ9gSOmFpCAFiEpRDW94ZNs0sEb+II3MgbXtORt5CFoLt6EzzLhl4t1aeEmvNBsQnWi1OkaIkNPpWzx5rY0OvW1cUKizSzbWRqO10Vlp4syPWoT6cucv0hWa5JojyE6MQyaDDzYKGOiT6jOJvylTO0=~1", "path": "/", "expiry": 1755628341},
    {"name": "bm_sz", "value": "64D49D52E7012EE228255E0300190448~YAAQpkg7FwNnpXiXAQAAfMm3hhxuq44sySwZtHGhKILwrIpR+nhX/TVLObw8J1APD2oiG39F0+jMcW6vVuRIe8ecIl5KNQ/ttZc0se4To5p27luS+IWmkklDdmbKFnqvCCLqyifya6P0z2zSb0tEyPi/8g5X0IQXgnYgLb7+RWslSROrWvy8CrmoAONGc1XzM7pne5mAszK742OycsCMxBSrsDJkbd/XdIO7+xawmBL70w4v+R3CLccIQqwzgKBUI9QDazXNyE5XRrppC9wizcwVqZF+CmaT3MlaUz6acJFKdJ2x6b5g5cmw42HeW0uzaJ/bKHKdhXK1ktZsZYB5c20FYowOr8uROJnKASgx9fDy2xb9NxmtTgsMq8kptU1UWmU037Nw2/0mFWZUH5XOAYu8Y2I+MCYuVPEZdV8mbJrXg6iSkEJR7n8=~3490356~4534329", "path": "/", "expiry": 1755630740},
    {"name": "cto_bundle", "value": "r5amLl9rM3BjcGEwUUhqaTVhVyUyQjdhMUFjcnZxd2pESVBnSlZabjFaOEJ0SlI0bkZ3eHhGN1F3N2x2NW5uaW1xWmNualQxcWhrVkF1MDZ4dzVVU1VOOTJvTHB1U3JiUkozeWtSOWU1djMzTXJBTk10ZHdRMTZaaktlZWNKbWJnNnZ2clN6eFlEajN4Z3FEZ0pPUEJjQjl6Mlg1USUzRCUzRA", "path": "/", "expiry": 1784453082},
    {"name": "MARKETID", "value": "17503111403910698900175", "path": "/", "expiry": 1784453561},
    {"name": "overrideAbTestGroup", "value": "%5B%5D", "path": "/", "expiry": 1755628941},
    {"name": "PCID", "value": "17503111403910698900175", "path": "/", "expiry": 1784456682},
    {"name": "sid", "value": "c6db1ac89dff4807bb470342303fb086b0f01a0b", "path": "/", "expiry": 1756069482},
    {"name": "web-session-id", "value": "9a2098f4-a98a-4b00-82d9-6a22c74adc14", "path": "/", "expiry": 1755628485},
    {"name": "x-coupang-accept-language", "value": "ko-KR", "path": "/", "expiry": 1758216282},
    {"name": "x-coupang-target-market", "value": "KR", "path": "/", "expiry": 1758215540},
]

PAGES_COUPANG_COOKIES = [
    {'name': '_abck', 'value': 'C722C8F883B5ACB82244C0B4D01E9931~-1~YAAQDdojF2eZq3uXAQAAv3yshg7OGUDUUAfYhgf2byuYCUDJtsEBYb+PV1XggYLMv3PDZ6B2+3rp+o+2i0X2AYHfCqHlT4wNYZZvMWJYg3uj5HPy0Rh0qMRPYBCbuOGsW3weqBtLgB+OTXZRgfkJc2e8Gz4nZINHx6ZUyRfECnRvtb71WjpLtXYmDvE+uxviFdc63FI7zlbN8vO1OWJjjrt+m5pnMMjSWHksO6ZlWqIgbWMosSzF/9pkPk3K+ERase93IQoLmyVp3dlfutpdAhUI4LEZx4HMBkJb68o2BHZK5xlfgvjrn5aU5WLtIOasojogkq/KMsmATeZcisSaFUjwapJ4UfLMH/N5DnxsEdTDaCrP9+62vwciS0nQpv1yfm+C545kS63HS5QKALJF6r6zfoMfW3f04JxOquihbyMd/Di5UKq5TYfKRLNHelq6Xi3O8yfW~-1~-1~-1', 'domain': '.coupang.com'},
    {'name': '_fbp', 'value': 'fb.1.1750311141345.554637432554019344', 'domain': '.coupang.com'},
    {'name': 'ak_bmsc', 'value': '6A3281A2776075873632E18F4A00B394~000000000000000000000000000000~YAAQDdojFwabq3uXAQAATn+shhxWOLViQV/LF4Pc3idFmeJVI+jzORNN+iD1FL+4Opg191bPffTDkaOUzVnyAFEuucBdg+4cCzND1RYFfYfIfLWYf7cAvMY4th1lRVXVusGFx9Ihb431EtB53JKlhtJuEi6LsZMIc5g1YRQXkE08+x3sxo3a7co5HROnp9E2/A4W9rhgl6Ex1B1bIDYus3kYAiM3cEYqm1mnDZP7zhRxywUGEGhJlo8AhupELMB3E1qDfKmd4/KNBnuuamBG4y9hQcH+psElKRKL+z90E19OmXI/B2QlF+nya/e15qRUe83jqqjY7OGyfVXbMKl7Z/DhXuUysDDFvyAZC8BbqKNmC0d2K3BB8cMwYsDTLLThX11M9GB8kbXaCIEODmBiyKp8//ZnqDkEd+jDyGt0YkJISoSNFD3+/xfBuZaYiE3M9BpPOxoiahLYuSre1xtH', 'domain': '.coupang.com'},
    {'name': 'baby-isWide', 'value': 'small', 'domain': '.coupang.com'},
    {'name': 'bm_lso', 'value': '4EC66251AD0D24EE07D4C6394CB1758067F5B4C665C5063C7163C46739474EEE~YAAQDdojF2qZq3uXAQAAv3yshgTe7jpyjeNiXQ1GPjqIYmYojkEIK5QaP5ncSyTY6940NJM3SAHXcNskqaE8le4azfOafBhBJjZ/NQPYF4j+9zczNLOiiJ0Ta31+zSZM/Nob6p9IEInVKkhOIZF6YpjKcg57BOtg/SqvWe4XE4hsVXj5VG/KeqeSWh8itG8uBw10o2DS68ZW187qDy/l7SnGUMv+rMNj0e4q8qTw1SKnEA8zPwBJsOlppIJ5RqNAye20Nz6t8N3vaiANhZFBN++yW7p4LT42vEC6VwBov2r/C8qmznTEOuEGRjCpeC/PJTmuHbbRJv1yJePe9YJmUj9mJIf7162NoO+BGmEoe9s1BdFb3E0xS6aph2S+0lxMCv3zomEOXbooxOXvHaifLsGzJ7UyWIS/7xuvNvU0zIF61p4uzvOBjGESkd5+FfiOZRc7xtnARdIyGzPr+5s9G7Y=^1750311140703', 'domain': '.pages.coupang.com'},
    {'name': 'bm_s', 'value': 'YAAQDdojFyicq3uXAQAAa4GshgPYxVo3acRkPgR4dUm61yTHicglZMkK42KVKvf58PFMnlhciO35ygcQV9+nUw/ZBKQeZZeV4+f72SbYckSLpyGi8ID2JVTnd/2aFeAFmwnjr92xbYEd9dm3u2fFxAsM2q6BUuomYgi5yOh7wV9Vj+xIijOZjS2cgzA+OQTBhJvAjP7vMj5lKiR/PaKnb0XNffuZfjY1N72zzvqDrRDCLuSwTB3TQ0VeH/rS5Plg4QUnGV36hYOAzHwtwr4apJoQvkEglUs+Ntg/EnXMdoMjnJqJdkrIWkM7XpWb8kEefo+X92MDDhX1qQddqJ0j+uZPn8z/saFolW5cEQqB35U0ur6P0J9AGWCwbT8A6843xOcVSZb+7pUNf4OVz5Khdy2I7tMDSrMObowtJYCan24MeNSs788wVnSWQL1B/yfwP/EobSW5qHsPOcsL+eSbWw4NKjYlRMxknTpKdOi7XjJR702WlJYUgViyBIGVHbCDshdBxd5vI+B7AHPIkVHJT4qw7+MEuacBe6SJMZPKuv/Yl2l7rUPRoFOHbw2l3vM=', 'domain': '.coupang.com'},
    {'name': 'bm_so', 'value': '4EC66251AD0D24EE07D4C6394CB1758067F5B4C665C5063C7163C46739474EEE~YAAQDdojF2qZq3uXAQAAv3yshgTe7jpyjeNiXQ1GPjqIYmYojkEIK5QaP5ncSyTY6940NJM3SAHXcNskqaE8le4azfOafBhBJjZ/NQPYF4j+9zczNLOiiJ0Ta31+zSZM/Nob6p9IEInVKkhOIZF6YpjKcg57BOtg/SqvWe4XE4hsVXj5VG/KeqeSWh8itG8uBw10o2DS68ZW187qDy/l7SnGUMv+rMNj0e4q8qTw1SKnEA8zPwBJsOlppIJ5RqNAye20Nz6t8N3vaiANhZFBN++yW7p4LT42vEC6VwBov2r/C8qmznTEOuEGRjCpeC/PJTmuHbbRJv1yJePe9YJmUj9mJIf7162NoO+BGmEoe9s1BdFb3E0xS6aph2S+0lxMCv3zomEOXbooxOXvHaifLsGzJ7UyWIS/7xuvNvU0zIF61p4uzvOBjGESkd5+FfiOZRc7xtnARdIyGzPr+5s9G7Y=', 'domain': '.coupang.com'},
    {'name': 'bm_ss', 'value': 'ab8e18ef4e', 'domain': '.coupang.com'},
    {'name': 'bm_sv', 'value': 'BFAE5765DB8C1217F08121DC0E765CBC~YAAQDdojFxCcq3uXAQAAGYGshhwTrJnfyGieVDeYvbs3fTRAU+3hB6/E2uGDEnhUQBvXk3axqDO6hF2ur0Yk24twhlYkcuV/hqOtS0xGokFhVqlBaV8QG6EoRyen+g1MovfjOeJ/0fnanyDWSdRrD8+oSk2HT+DlIxNmT2lXAgbtPvwWvA4R6epfR0yEPPXa4eR2Wzr9DrPFu/ZMhmLSNq/JyGTBxZPCekFk+Fyv9nlGM5KpvECbtN8XTC37cW6/IA==~1', 'domain': '.coupang.com'},
    {'name': 'bm_sz', 'value': '64D49D52E7012EE228255E0300190448~YAAQDdojF2uZq3uXAQAAv3yshhwhk4ZpHtIXIqUJO11HUy4OOmh2jj9Jlt0e7NH8Ve1pERXQPcHdrIwjfksxY5pek6OYJiDOZ/V6hbo6ncQ5qJg2FubQfUJ+gy2LcZio9RF1d/B5rkO71eDOZw6lYGKbP1QJ9bpMOx62nOgyPiDdnOuX+Ey1S3WJsI1F2DP3aV0bvykpLJlwnzi1RiK9sO6xQ5MX+HuzMQ7JuGG9CVZKCGAa5j7OXWkWhAQ/2uT/44Vp66JaqzhvikFx9LvdCw27W6vBzTFjaewEv7bHcNQrYlWKMVldbzlRUkgXOjDiPuXKL3J6nnS3IJDIf70ILwYYsOdaPgZr/+xPeVf8JY4CS3vFUl1LbIvA6SxbpM/YSXSJnPtJK1T02DT4aNhfPo8l~3490356~4534329', 'domain': '.coupang.com'},
    {'name': 'cto_bundle', 'value': 'eeEtE19rM3BjcGEwUUhqaTVhVyUyQjdhMUFjcnF6cklHc01lZUxoSENmQ2FmMm0xUlpRRHN3bWFVMXc1Q0MxVmp5YVlBVCUyRk9YaVpaT1YxNHFyRXRoUmtURmp6TVdQYTk2OXZDaE5MRWFGeG52cFViY1YlMkJzTXg1bG52cHpUdnE5bmY1MmtqNiUyRmdVMEFhcldwZXNHVjZhWkdrcVVSbVFEQyUyQjlNZHh1QURGZkExbVZRSG9PRmcyaU81NUw5aHdIR2VGRERBbFpTdnU2NlFGVDZjemxQOGFpNmprN1B3dyUzRCUzRA', 'domain': '.coupang.com'},
    {'name': 'MARKETID', 'value': '17503111403910698900175', 'domain': '.coupang.com'},
    {'name': 'overrideAbTestGroup', 'value': '%5B%5D', 'domain': '.coupang.com'},
    {'name': 'PCID', 'value': '17503111403910698900175', 'domain': '.coupang.com'},
    {'name': 'sid', 'value': 'c6db1ac89dff4807bb470342303fb086b0f01a0b', 'domain': '.coupang.com'},
    {'name': 'x-coupang-accept-language', 'value': 'ko-KR', 'domain': '.coupang.com'},
    {'name': 'x-coupang-target-market', 'value': 'KR', 'domain': '.coupang.com'},
]

def get_coupang_cookies(domain: str):
    """
    도메인에 따라 알맞은 쿠키 리스트를 반환합니다.
    domain: 'www.coupang.com', 'coupang.com', 'pages.coupang.com' 등
    """
    if "pages.coupang.com" in domain:
        return PAGES_COUPANG_COOKIES
    return COUPANG_COOKIES 

def parse_cookies_from_text(cookie_text: str):
    """
    크롬에서 복사한 쿠키 텍스트(탭 또는 쉼표 구분)를 파싱해서
    셀레니움 add_cookie용 dict 리스트로 변환
    """
    cookies = []
    lines = cookie_text.strip().splitlines()
    for line in lines:
        # 탭 또는 쉼표 구분
        parts = line.split('\t') if '\t' in line else line.split(',')
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        value = parts[1].strip()
        cookie = {'name': name, 'value': value}
        # path
        if len(parts) > 3:
            cookie['path'] = parts[3].strip()
        # expiry (ISO8601 → timestamp)
        if len(parts) > 4 and parts[4]:
            try:
                dt = datetime.datetime.fromisoformat(parts[4].replace('Z', '+00:00'))
                cookie['expiry'] = int(dt.timestamp())
            except Exception:
                pass
        cookies.append(cookie)
    return cookies 