# 
# python3 get_bibtex_from_ads.py

import requests
import os
import pyperclip
def get_bibtex_from_ads(doi):
    """
    通过DOI从ADS获取BibTeX条目
    """
    # ADS API端点
    url = "https://api.adsabs.harvard.edu/v1/search/query"
    
    # 查询参数
    params = {
        'q': f'doi:"{doi}"',
        'fl': 'bibcode',
        'rows': 1
    }
    
    # 需要ADS API token
    headers = {
        'Authorization': 'Bearer ' + os.getenv('ADS_API_TOKEN', 'YourToken')
    }
    
    try:
        # 第一步：搜索获取bibcode
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        if not data['response']['docs']:
            print(f"未找到DOI为 {doi} 的文献")
            return None
        
        bibcode = data['response']['docs'][0]['bibcode']
        
        # 第二步：获取BibTeX格式
        export_url = f"https://api.adsabs.harvard.edu/v1/export/bibtex"
        export_params = {
            'bibcode': [bibcode]
        }
        
        export_response = requests.post(export_url, json=export_params, headers=headers)
        export_response.raise_for_status()
        
        bibtex_data = export_response.json()
        bibtex_content = bibtex_data['export']
        
        return bibtex_content
        
    except Exception as e:
        print(f"错误: {e}")
        return None

def main():
    # 使用input()获取用户输入
    doi = input("请输入DOI: ").strip()
    
    if not doi:
        print("DOI不能为空")
        return
    
    print(f"正在查找DOI: {doi}")
    
    bibtex = get_bibtex_from_ads(doi)
    
    if bibtex:
        pyperclip.copy(bibtex)
        print("=" * 50)
        print(bibtex)
        print("=" * 50)
        print("BibTeX已复制到剪贴板")
    else:
        print("请提供DOI参数")

if __name__ == "__main__":
    main()
    
    
    
    
    