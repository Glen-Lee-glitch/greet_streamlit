import sqlite3
import os
from datetime import datetime


class DatabaseManager:
    """SQLite3 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path='data.db'):
        """데이터베이스 연결 초기화"""
        self.db_path = db_path
        self.connection = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """데이터베이스에 연결"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            print(f"데이터베이스 '{self.db_path}'에 연결되었습니다.")
        except sqlite3.Error as e:
            print(f"데이터베이스 연결 오류: {e}")
    
    def create_tables(self):
        """모든 테이블 생성"""
        if not self.connection:
            print("데이터베이스 연결이 없습니다.")
            return
        
        cursor = self.connection.cursor()
        
        try:
            # 1. 파이프라인 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS 파이프라인 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    날짜 DATE NOT NULL,
                    파이프라인 INTEGER NOT NULL
                )
            ''')
            
            # 2. 지원신청 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS 지원신청 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    날짜 DATE NOT NULL,
                    지원신청 INTEGER NOT NULL,
                    PAK_내부지원 INTEGER NOT NULL,
                    접수후취소 INTEGER NOT NULL,
                    미신청건 INTEGER NOT NULL,
                    보완 INTEGER NOT NULL
                )
            ''')
            
            # 3. 특이사항 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS 특이사항 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    날짜 DATE NOT NULL,
                    특이사항 TEXT NOT NULL,
                    건 INTEGER NOT NULL
                )
            ''')
            
            # 4. 테슬라_지급 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS 테슬라_지급 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    날짜 TEXT NOT NULL UNIQUE,
                    배분 INTEGER DEFAULT 0,
                    신청 INTEGER DEFAULT 0,
                    지급_잔여 INTEGER DEFAULT 0
                )
            ''')

            self.connection.commit()
            print("모든 테이블이 성공적으로 생성되었습니다.")
            
        except sqlite3.Error as e:
            print(f"테이블 생성 오류: {e}")
    
    def insert_pipeline_data(self, 날짜, 파이프라인):
        """파이프라인 테이블에 데이터 삽입"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO 파이프라인 (날짜, 파이프라인)
                VALUES (?, ?)
            ''', (날짜, 파이프라인))
            self.connection.commit()
            print(f"파이프라인 데이터 삽입 완료: {날짜}, {파이프라인}")
        except sqlite3.Error as e:
            print(f"파이프라인 데이터 삽입 오류: {e}")
    
    def insert_support_data(self, 날짜, 지원신청, pak_내부지원, 접수후취소, 미신청건, 보완):
        """지원신청 테이블에 데이터 삽입"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO 지원신청 (날짜, 지원신청, PAK_내부지원, 접수후취소, 미신청건, 보완)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (날짜, 지원신청, pak_내부지원, 접수후취소, 미신청건, 보완))
            self.connection.commit()
            print(f"지원신청 데이터 삽입 완료: {날짜}")
        except sqlite3.Error as e:
            print(f"지원신청 데이터 삽입 오류: {e}")
    
    def insert_special_data(self, 날짜, 특이사항, 건):
        """특이사항 테이블에 데이터 삽입"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO 특이사항 (날짜, 특이사항, 건)
                VALUES (?, ?, ?)
            ''', (날짜, 특이사항, 건))
            self.connection.commit()
            print(f"특이사항 데이터 삽입 완료: {날짜}, {특이사항}")
        except sqlite3.Error as e:
            print(f"특이사항 데이터 삽입 오류: {e}")

    def insert_tesla_data(self, 날짜, 배분, 신청, 지급_잔여):
        """테슬라_지급 테이블에 데이터 삽입"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO 테슬라_지급 (날짜, 배분, 신청, 지급_잔여)
                VALUES (?, ?, ?, ?)
            ''', (날짜, 배분, 신청, 지급_잔여))
            self.connection.commit()
            print(f"테슬라_지급 데이터 삽입 완료: {날짜}")
        except sqlite3.Error as e:
            print(f"테슬라_지급 데이터 삽입 오류: {e}")
    
    def get_pipeline_data(self, start_date=None, end_date=None):
        """파이프라인 데이터 조회"""
        cursor = self.connection.cursor()
        try:
            if start_date and end_date:
                cursor.execute('''
                    SELECT * FROM 파이프라인 
                    WHERE 날짜 BETWEEN ? AND ?
                    ORDER BY 날짜
                ''', (start_date, end_date))
            else:
                cursor.execute('SELECT * FROM 파이프라인 ORDER BY 날짜')
            
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"파이프라인 데이터 조회 오류: {e}")
            return []
    
    def get_support_data(self, start_date=None, end_date=None):
        """지원신청 데이터 조회"""
        cursor = self.connection.cursor()
        try:
            if start_date and end_date:
                cursor.execute('''
                    SELECT * FROM 지원신청 
                    WHERE 날짜 BETWEEN ? AND ?
                    ORDER BY 날짜
                ''', (start_date, end_date))
            else:
                cursor.execute('SELECT * FROM 지원신청 ORDER BY 날짜')
            
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"지원신청 데이터 조회 오류: {e}")
            return []
    
    def get_special_data(self, start_date=None, end_date=None):
        """특이사항 데이터 조회"""
        cursor = self.connection.cursor()
        try:
            if start_date and end_date:
                cursor.execute('''
                    SELECT * FROM 특이사항 
                    WHERE 날짜 BETWEEN ? AND ?
                    ORDER BY 날짜
                ''', (start_date, end_date))
            else:
                cursor.execute('SELECT * FROM 특이사항 ORDER BY 날짜')
            
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"특이사항 데이터 조회 오류: {e}")
            return []

    def get_tesla_data(self, start_date=None, end_date=None):
        """테슬라_지급 데이터 조회"""
        cursor = self.connection.cursor()
        try:
            if start_date and end_date:
                cursor.execute('''
                    SELECT * FROM 테슬라_지급 
                    WHERE 날짜 BETWEEN ? AND ?
                    ORDER BY 날짜
                ''', (start_date, end_date))
            else:
                cursor.execute('SELECT * FROM 테슬라_지급 ORDER BY 날짜')
            
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"테슬라_지급 데이터 조회 오류: {e}")
            return []
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.connection:
            self.connection.close()
            print("데이터베이스 연결이 종료되었습니다.")


# 사용 예시
if __name__ == "__main__":
    # 데이터베이스 매니저 인스턴스 생성
    db = DatabaseManager()
    
    # 예시 데이터 삽입
    # db.insert_pipeline_data('2025-01-15', 150)
    # db.insert_support_data('2025-01-15', 120, 30, 5, 10, 8)
    # db.insert_special_data('2025-01-15', '시스템 점검으로 인한 지연', 3)
    
    # 데이터 조회
    print("\n=== 파이프라인 데이터 ===")
    pipeline_data = db.get_pipeline_data()
    for row in pipeline_data:
        print(row)
    
    print("\n=== 지원신청 데이터 ===")
    support_data = db.get_support_data()
    for row in support_data:
        print(row)
    
    print("\n=== 특이사항 데이터 ===")
    special_data = db.get_special_data()
    for row in special_data:
        print(row)
    
    # 연결 종료
    db.close()