# Developer 라는 개발자 클래스를 정의하려고 함.
# 내부에서 id, title, skills 변수가 있고, 이내용을 출력하는
# Printing()메서드가 필요해
Class Developer:
    def __init__(self, id, title, skills):
        self.id = id
        self.title = title
        self.skills = skills

    def Printing(self):
        print(f"ID: {self.id}")
        print(f"Title: {self.title}")
        print(f"Skills: {', '.join(self.skills)}")

#인스턴트롤 생성(디버깅하는 모드로 실행하면 중단점)
def = Developer(1, "Blckend Developer", 
                )