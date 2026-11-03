@echo off
rem 네이버 뉴스 크롤러를 실행파일(dist\NaverNewsCrawler.exe) 하나로 만든다.
cd /d "%~dp0"

rem 필요한 패키지가 없으면 설치한다
python -m pip install pyinstaller requests beautifulsoup4 PyQt6 openpyxl || goto :error

rem --onefile  : exe 파일 하나로 묶기
rem --windowed : 실행할 때 검은 콘솔 창을 띄우지 않기
rem --add-data : 창 아이콘 파일을 exe 안에 포함하기
rem --exclude-module : openpyxl이 있으면 가져다 쓰는 numpy, PIL은 이 앱에 필요 없으므로 빼서 용량을 줄이기
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name NaverNewsCrawler ^
    --icon naver_news_crawler.ico ^
    --add-data "naver_news_crawler.ico;." ^
    --exclude-module numpy --exclude-module PIL ^
    naver_news_crawler.py || goto :error

echo.
echo 완료: dist\NaverNewsCrawler.exe
exit /b 0

:error
echo.
echo 빌드에 실패했습니다.
exit /b 1
