import sys
import calendar
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                           QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem, 
                           QPushButton, QMessageBox, QHeaderView, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QAction
from db_manager import DatabaseManager


class DatabaseManagementApp(QMainWindow):
    """데이터베이스 관리 PyQt6 애플리케이션"""
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.is_edit_mode = False
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle('데이터베이스 관리 시스템')
        self.setGeometry(100, 100, 1200, 800)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        layout = QVBoxLayout(central_widget)
        
        # 컨트롤 버튼들
        self.create_control_buttons(layout)
        
        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 각 탭 생성
        self.create_pipeline_tab()
        self.create_support_tab()
        self.create_special_tab()
        
        # 기본 폰트 설정
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
    
    def create_control_buttons(self, layout):
        """컨트롤 버튼들 생성"""
        button_layout = QHBoxLayout()
        
        # 수정 버튼
        self.edit_button = QPushButton('수정')
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        self.edit_button.setMinimumHeight(40)
        
        # 업데이트 버튼
        self.update_button = QPushButton('업데이트')
        self.update_button.clicked.connect(self.update_database)
        self.update_button.setEnabled(False)
        self.update_button.setMinimumHeight(40)
        
        # 새로고침 버튼
        self.refresh_button = QPushButton('새로고침')
        self.refresh_button.clicked.connect(self.load_data)
        self.refresh_button.setMinimumHeight(40)
        
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def create_pipeline_tab(self):
        """파이프라인 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 테이블 위젯
        self.pipeline_table = QTableWidget()
        self.pipeline_table.setColumnCount(2)
        self.pipeline_table.setHorizontalHeaderLabels(['날짜', '파이프라인'])
        
        # 8월 전체 날짜 (31일) + 합계 행 생성
        self.pipeline_table.setRowCount(32)  # 31일 + 합계행
        
        # 날짜 자동 채우기
        for day in range(1, 32):
            date_str = f"2025-08-{day:02d}"
            date_item = QTableWidgetItem(date_str)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # 날짜는 수정 불가
            self.pipeline_table.setItem(day-1, 0, date_item)
            
            # 파이프라인 값 (기본 0)
            pipeline_item = QTableWidgetItem("0")
            self.pipeline_table.setItem(day-1, 1, pipeline_item)
        
        # 합계 행 추가
        total_date_item = QTableWidgetItem("합계")
        total_date_item.setFlags(total_date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pipeline_table.setItem(31, 0, total_date_item)
        
        total_pipeline_item = QTableWidgetItem("0")
        total_pipeline_item.setFlags(total_pipeline_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pipeline_table.setItem(31, 1, total_pipeline_item)
        
        # 테이블 설정
        self.setup_table(self.pipeline_table)
        self.style_total_row(self.pipeline_table, 31)
        layout.addWidget(self.pipeline_table)
        
        self.tab_widget.addTab(tab, '파이프라인')
    
    def create_support_tab(self):
        """지원신청 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 테이블 위젯
        self.support_table = QTableWidget()
        self.support_table.setColumnCount(6)
        self.support_table.setHorizontalHeaderLabels([
            '날짜', '지원신청', 'PAK 내부지원', '접수 후 취소', '미신청건', '보완'
        ])
        
        # 8월 전체 날짜 (31일) + 합계 행 생성
        self.support_table.setRowCount(32)  # 31일 + 합계행
        
        # 날짜 자동 채우기
        for day in range(1, 32):
            date_str = f"2025-08-{day:02d}"
            date_item = QTableWidgetItem(date_str)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # 날짜는 수정 불가
            self.support_table.setItem(day-1, 0, date_item)
            
            # 나머지 컬럼들 (기본 0)
            for col in range(1, 6):
                item = QTableWidgetItem("0")
                self.support_table.setItem(day-1, col, item)
        
        # 합계 행 추가
        total_date_item = QTableWidgetItem("합계")
        total_date_item.setFlags(total_date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.support_table.setItem(31, 0, total_date_item)
        
        # 각 컬럼별 합계 초기화
        for col in range(1, 6):
            total_item = QTableWidgetItem("0")
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.support_table.setItem(31, col, total_item)
        
        # 테이블 설정
        self.setup_table(self.support_table)
        self.style_total_row(self.support_table, 31)
        layout.addWidget(self.support_table)
        
        self.tab_widget.addTab(tab, '지원신청')
    
    def create_special_tab(self):
        """특이사항 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 테이블 위젯
        self.special_table = QTableWidget()
        self.special_table.setColumnCount(3)
        self.special_table.setHorizontalHeaderLabels(['날짜', '특이사항', '건'])
        
        # 초기에는 빈 테이블로 시작
        self.special_table.setRowCount(0)
        
        # 테이블 설정
        self.setup_table(self.special_table)
        
        # 특이사항 추가/삭제 버튼
        button_layout = QHBoxLayout()
        
        add_row_btn = QPushButton('행 추가')
        add_row_btn.clicked.connect(self.add_special_row)
        
        remove_row_btn = QPushButton('선택 행 삭제')
        remove_row_btn.clicked.connect(self.remove_special_row)
        
        button_layout.addWidget(add_row_btn)
        button_layout.addWidget(remove_row_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addWidget(self.special_table)
        
        # 특이사항 테이블에도 컨텍스트 메뉴 추가
        self.special_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.special_table.customContextMenuRequested.connect(self.show_special_context_menu)
        
        self.tab_widget.addTab(tab, '특이사항')
    
    def setup_table(self, table):
        """테이블 공통 설정"""
        # 헤더 설정
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        
        # 기본적으로 수정 불가능하게 설정
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 선택 모드 설정
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # 스타일 설정
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: #fafafa;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        
        # 데이터 변경 시 합계 자동 계산을 위한 시그널 연결
        table.itemChanged.connect(self.calculate_totals)
        
        # 컨텍스트 메뉴 활성화
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_context_menu)
    
    def style_total_row(self, table, row_index):
        """합계 행 스타일링"""
        for col in range(table.columnCount()):
            item = table.item(row_index, col)
            if item:
                # 합계 행에 굵은 글씨와 배경색 적용
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setBackground(Qt.GlobalColor.lightGray)
    
    def calculate_totals(self, item):
        """합계 자동 계산"""
        table = item.tableWidget()
        
        # 파이프라인 테이블 합계 계산
        if table == self.pipeline_table:
            total = 0
            for row in range(31):  # 합계 행 제외
                pipeline_item = table.item(row, 1)
                if pipeline_item and pipeline_item.text().isdigit():
                    total += int(pipeline_item.text())
            
            total_item = table.item(31, 1)
            if total_item:
                total_item.setText(str(total))
                
        # 지원신청 테이블 합계 계산
        elif table == self.support_table:
            for col in range(1, 6):  # 각 숫자 컬럼별로 합계 계산
                total = 0
                for row in range(31):  # 합계 행 제외
                    item_value = table.item(row, col)
                    if item_value and item_value.text().isdigit():
                        total += int(item_value.text())
                
                total_item = table.item(31, col)
                if total_item:
                    total_item.setText(str(total))
    
    def calculate_pipeline_total(self):
        """파이프라인 테이블 합계 계산"""
        total = 0
        for row in range(31):  # 합계 행 제외
            pipeline_item = self.pipeline_table.item(row, 1)
            if pipeline_item and pipeline_item.text().isdigit():
                total += int(pipeline_item.text())
        
        total_item = self.pipeline_table.item(31, 1)
        if total_item:
            total_item.setText(str(total))
    
    def calculate_support_total(self):
        """지원신청 테이블 합계 계산"""
        for col in range(1, 6):  # 각 숫자 컬럼별로 합계 계산
            total = 0
            for row in range(31):  # 합계 행 제외
                item_value = self.support_table.item(row, col)
                if item_value and item_value.text().isdigit():
                    total += int(item_value.text())
            
            total_item = self.support_table.item(31, col)
            if total_item:
                total_item.setText(str(total))
    
    def show_context_menu(self, position):
        """컨텍스트 메뉴 표시"""
        table = self.sender()
        if not table:
            return
        
        # 클릭된 위치의 행 확인
        row = table.rowAt(position.y())
        if row < 0 or row >= 31:  # 합계 행이나 범위 밖은 제외
            return
        
        # 컨텍스트 메뉴 생성
        context_menu = QMenu(self)
        
        # 공휴일/주말 제거 액션
        remove_action = QAction("공휴일/주말 제거", self)
        remove_action.triggered.connect(lambda: self.remove_holiday_weekend(table, row))
        context_menu.addAction(remove_action)
        
        # 메뉴 표시
        context_menu.exec(table.mapToGlobal(position))
    
    def remove_holiday_weekend(self, table, row):
        """공휴일/주말 행 제거"""
        if not self.is_edit_mode:
            QMessageBox.warning(self, '경고', '수정 모드에서만 행을 제거할 수 있습니다.')
            return
        
        # 해당 행의 날짜 확인
        date_item = table.item(row, 0)
        if not date_item:
            return
        
        date_str = date_item.text()
        
        # 공휴일/주말 여부 확인
        if self.is_holiday_or_weekend(date_str):
            # 행 제거
            table.removeRow(row)
            
            # 새로운 행 추가 (맨 아래, 합계 행 위)
            new_row = table.rowCount() - 1
            table.insertRow(new_row)
            
            # 기본값으로 새 행 설정
            if table == self.pipeline_table:
                # 파이프라인 테이블
                table.setItem(new_row, 0, QTableWidgetItem(""))
                table.setItem(new_row, 1, QTableWidgetItem("0"))
            elif table == self.support_table:
                # 지원신청 테이블
                table.setItem(new_row, 0, QTableWidgetItem(""))
                for col in range(1, 6):
                    table.setItem(new_row, col, QTableWidgetItem("0"))
            
            # 합계 재계산
            if table == self.pipeline_table:
                self.calculate_pipeline_total()
            elif table == self.support_table:
                self.calculate_support_total()
                
            QMessageBox.information(self, '완료', f'{date_str} 행이 제거되었습니다.')
        else:
            QMessageBox.information(self, '알림', f'{date_str}은 공휴일이나 주말이 아닙니다.')
    
    def is_holiday_or_weekend(self, date_str):
        """공휴일이나 주말인지 확인"""
        try:
            # 날짜 파싱
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            # 주말 확인 (토요일=5, 일요일=6)
            if date_obj.weekday() >= 5:
                return True
            
            # 2025년 8월 공휴일 목록
            holidays_2025_08 = [
                '2025-08-15',  # 광복절
            ]
            
            if date_str in holidays_2025_08:
                return True
                
            return False
            
        except ValueError:
            return False
    
    def show_special_context_menu(self, position):
        """특이사항 테이블 컨텍스트 메뉴 표시"""
        if not self.is_edit_mode:
            QMessageBox.warning(self, '경고', '수정 모드에서만 컨텍스트 메뉴를 사용할 수 있습니다.')
            return
        
        # 클릭된 위치의 행 확인
        row = self.special_table.rowAt(position.y())
        if row < 0:
            return
        
        # 컨텍스트 메뉴 생성
        context_menu = QMenu(self)
        
        # 행 삭제 액션
        remove_action = QAction("행 삭제", self)
        remove_action.triggered.connect(lambda: self.remove_special_row_at(row))
        context_menu.addAction(remove_action)
        
        # 메뉴 표시
        context_menu.exec(self.special_table.mapToGlobal(position))
    
    def remove_special_row_at(self, row):
        """특정 행 번호로 특이사항 행 삭제"""
        if row >= 0 and row < self.special_table.rowCount():
            self.special_table.removeRow(row)
    
    def toggle_edit_mode(self):
        """수정 모드 토글"""
        self.is_edit_mode = not self.is_edit_mode
        
        if self.is_edit_mode:
            # 수정 모드 활성화
            self.edit_button.setText('수정 취소')
            self.update_button.setEnabled(True)
            
            # 테이블들을 수정 가능하게 설정 (날짜 컬럼 제외)
            self.set_table_editable(self.pipeline_table, True)
            self.set_table_editable(self.support_table, True)
            self.set_table_editable(self.special_table, True, exclude_date=False)
            
        else:
            # 수정 모드 비활성화
            self.edit_button.setText('수정')
            self.update_button.setEnabled(False)
            
            # 테이블들을 읽기 전용으로 설정
            self.set_table_editable(self.pipeline_table, False)
            self.set_table_editable(self.support_table, False)
            self.set_table_editable(self.special_table, False)
    
    def set_table_editable(self, table, editable, exclude_date=True):
        """테이블의 수정 가능 상태 설정"""
        if editable:
            table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | 
                                QTableWidget.EditTrigger.EditKeyPressed)
            
            # 날짜 컬럼은 항상 수정 불가능하게 유지 (특이사항 테이블 제외)
            if exclude_date:
                for row in range(table.rowCount()):
                    date_item = table.item(row, 0)
                    if date_item:
                        date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        else:
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    
    def add_special_row(self):
        """특이사항 테이블에 새 행 추가"""
        if not self.is_edit_mode:
            QMessageBox.warning(self, '경고', '수정 모드에서만 행을 추가할 수 있습니다.')
            return
        
        row_count = self.special_table.rowCount()
        self.special_table.insertRow(row_count)
        
        # 기본값 설정
        today = datetime.now().strftime('%Y-%m-%d')
        self.special_table.setItem(row_count, 0, QTableWidgetItem(today))
        self.special_table.setItem(row_count, 1, QTableWidgetItem(''))
        self.special_table.setItem(row_count, 2, QTableWidgetItem('0'))
    
    def remove_special_row(self):
        """특이사항 테이블에서 선택된 행 삭제"""
        if not self.is_edit_mode:
            QMessageBox.warning(self, '경고', '수정 모드에서만 행을 삭제할 수 있습니다.')
            return
        
        current_row = self.special_table.currentRow()
        if current_row >= 0:
            self.special_table.removeRow(current_row)
    
    def load_data(self):
        """데이터베이스에서 데이터 로드"""
        try:
            # 파이프라인 데이터 로드
            pipeline_data = self.db_manager.get_pipeline_data()
            pipeline_dict = {row[1]: row[2] for row in pipeline_data}  # 날짜: 파이프라인
            
            for row in range(31):  # 합계 행 제외하고 로드
                date_item = self.pipeline_table.item(row, 0)
                if date_item:
                    date_str = date_item.text()
                    pipeline_value = pipeline_dict.get(date_str, 0)
                    self.pipeline_table.setItem(row, 1, QTableWidgetItem(str(pipeline_value)))
            
            # 파이프라인 합계 계산
            self.calculate_pipeline_total()
            
            # 지원신청 데이터 로드
            support_data = self.db_manager.get_support_data()
            support_dict = {}
            for row in support_data:
                support_dict[row[1]] = [row[2], row[3], row[4], row[5], row[6]]  # 날짜: [지원신청, PAK내부지원, 접수후취소, 미신청건, 보완]
            
            for row in range(31):  # 합계 행 제외하고 로드
                date_item = self.support_table.item(row, 0)
                if date_item:
                    date_str = date_item.text()
                    support_values = support_dict.get(date_str, [0, 0, 0, 0, 0])
                    for col in range(1, 6):
                        self.support_table.setItem(row, col, QTableWidgetItem(str(support_values[col-1])))
            
            # 지원신청 합계 계산
            self.calculate_support_total()
            
            # 특이사항 데이터 로드
            special_data = self.db_manager.get_special_data()
            self.special_table.setRowCount(len(special_data))
            
            for row, data in enumerate(special_data):
                self.special_table.setItem(row, 0, QTableWidgetItem(data[1]))  # 날짜
                self.special_table.setItem(row, 1, QTableWidgetItem(data[2]))  # 특이사항
                self.special_table.setItem(row, 2, QTableWidgetItem(str(data[3])))  # 건
            
            print("데이터가 성공적으로 로드되었습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, '오류', f'데이터 로드 중 오류가 발생했습니다: {str(e)}')
    
    def update_database(self):
        """데이터베이스 업데이트"""
        try:
            # 파이프라인 데이터 업데이트 (합계 행 제외)
            for row in range(31):  # 합계 행 제외
                date_item = self.pipeline_table.item(row, 0)
                pipeline_item = self.pipeline_table.item(row, 1)
                
                if date_item and pipeline_item:
                    date_str = date_item.text()
                    pipeline_value = int(pipeline_item.text() or 0)
                    
                    # 기존 데이터 삭제 후 새로 삽입
                    cursor = self.db_manager.connection.cursor()
                    cursor.execute('DELETE FROM 파이프라인 WHERE 날짜 = ?', (date_str,))
                    self.db_manager.insert_pipeline_data(date_str, pipeline_value)
            
            # 지원신청 데이터 업데이트 (합계 행 제외)
            for row in range(31):  # 합계 행 제외
                date_item = self.support_table.item(row, 0)
                
                if date_item:
                    date_str = date_item.text()
                    values = []
                    
                    for col in range(1, 6):
                        item = self.support_table.item(row, col)
                        values.append(int(item.text() or 0) if item else 0)
                    
                    # 기존 데이터 삭제 후 새로 삽입
                    cursor = self.db_manager.connection.cursor()
                    cursor.execute('DELETE FROM 지원신청 WHERE 날짜 = ?', (date_str,))
                    self.db_manager.insert_support_data(date_str, *values)
            
            # 특이사항 데이터 업데이트 (전체 삭제 후 재삽입)
            cursor = self.db_manager.connection.cursor()
            cursor.execute('DELETE FROM 특이사항')
            
            for row in range(self.special_table.rowCount()):
                date_item = self.special_table.item(row, 0)
                special_item = self.special_table.item(row, 1)
                count_item = self.special_table.item(row, 2)
                
                if date_item and special_item and count_item:
                    date_str = date_item.text()
                    special_text = special_item.text()
                    count_value = int(count_item.text() or 0)
                    
                    if special_text.strip():  # 빈 특이사항은 저장하지 않음
                        self.db_manager.insert_special_data(date_str, special_text, count_value)
            
            # 수정 모드 비활성화
            self.toggle_edit_mode()
            
            QMessageBox.information(self, '성공', '데이터가 성공적으로 업데이트되었습니다.')
            
        except Exception as e:
            QMessageBox.critical(self, '오류', f'데이터 업데이트 중 오류가 발생했습니다: {str(e)}')
    
    def closeEvent(self, event):
        """애플리케이션 종료 시 데이터베이스 연결 해제"""
        self.db_manager.close()
        event.accept()


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    
    # 애플리케이션 스타일 설정
    app.setStyle('Fusion')
    
    window = DatabaseManagementApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
