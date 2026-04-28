"""
생성된 데이터셋 통계 및 분석
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "data"

def analyze_dataset(filepath):
    """데이터셋 분석"""
    try:
        df = pd.read_csv(filepath)
        
        stats = {
            '파일': filepath.name,
            '행 수': len(df),
            '열 수': len(df.columns),
            '메모리(MB)': df.memory_usage(deep=True).sum() / 1024**2,
            '결측치': df.isnull().sum().sum(),
        }
        
        if 'label' in df.columns:
            normal = (df['label'] == 0).sum()
            anomaly = (df['label'] == 1).sum()
            stats['정상:이상'] = f"{normal}:{anomaly} ({anomaly/len(df)*100:.1f}%)"
        
        return stats
    except Exception as e:
        return {'파일': filepath.name, '오류': str(e)}

def main():
    print("="*80)
    print("📊 Anomaly Detection 데이터셋 분석 리포트")
    print("="*80)
    
    categories = {
        '🕐 시계열 (단변량)': BASE_DIR / 'timeseries' / 'univariate' / 'raw',
        '🕐 시계열 (다변량)': BASE_DIR / 'timeseries' / 'multivariate' / 'raw',
        '🔢 수치형 (테이블)': BASE_DIR / 'numerical' / 'tabular' / 'raw',
        '🔢 수치형 (고차원)': BASE_DIR / 'numerical' / 'high_dim' / 'raw',
        '🏷️  혼합형 (카테고리)': BASE_DIR / 'categorical' / 'mixed' / 'raw',
    }
    
    total_files = 0
    total_rows = 0
    
    for category, path in categories.items():
        if not path.exists():
            continue
        
        print(f"\n{category}")
        print("-" * 80)
        
        csv_files = list(path.glob('*.csv'))
        
        if not csv_files:
            print("  파일 없음")
            continue
        
        for csv_file in sorted(csv_files):
            stats = analyze_dataset(csv_file)
            
            if '오류' in stats:
                print(f"  ✗ {stats['파일']}: {stats['오류']}")
            else:
                print(f"  ✓ {stats['파일']}")
                print(f"    크기: {stats['행 수']:,} 행 × {stats['열 수']} 열 ({stats['메모리(MB)']:.2f} MB)")
                if '정상:이상' in stats:
                    print(f"    데이터: {stats['정상:이상']}")
                
                total_files += 1
                total_rows += stats['행 수']
    
    print("\n" + "="*80)
    print(f"📈 전체 요약")
    print("="*80)
    print(f"  총 파일 수: {total_files}")
    print(f"  총 행 수: {total_rows:,}")
    print(f"\n✅ data/ 폴더의 모든 데이터셋이 준비되었습니다!")
    print(f"\n📖 상세 정보: data/README.md")
    print(f"📚 활용 가이드: DATA_SETUP_REPORT.md")

if __name__ == "__main__":
    main()
