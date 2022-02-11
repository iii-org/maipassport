import random, string
from maipassport.citadel.services import logger_writer
from maipassport.core.exceptions import (CompanyNotExists, CreateDepartmentFailed, CreatePlaceFailed,
                                         CompanyAlreadyExists, CompanyTitleAlreadyExists, UserNotExists,
                                         DepartmentNotExists, TitleNotExists, DepartmentAlreadyExists,
                                         UserAttendanceStatusAlreadyExists)
from maipassport.companies.models import (Company, Department, Title, Place, UserCompanyTable, AddCompanyTag,
                                          CompanyDefaultPrint)
from maipassport.users.models import AppUser, AttendanceStatus
from maipassport.users.services import AppUserServices


class CompanyServices:

    @staticmethod
    def create_department(department_name, company_id, company=None):
        if not company:
            company = Company.objects.filter(pub_id=company_id)
            if company.exists():
                company = company.first()
            else:
                raise CompanyNotExists
        try:
            if Department.objects.filter(name=department_name, company=company).exists():
                raise DepartmentAlreadyExists
            department = Department.objects.create(name=department_name, company=company)
        except Exception as e:
            logger_writer('SYSTEM', 'error', 'CREATE_DEPARTMENT', f'Create department got error: {str(e)}')
            raise CreateDepartmentFailed
        else:
            return department

    @staticmethod
    def create_place(place_name, address=None, company_id=None, company=None):
        try:
            serial_num = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(6)).upper()
            while Place.objects.filter(serial_num=serial_num).exists():
                serial_num = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(6)).upper()
            place = Place.objects.create(name=place_name, serial_num=serial_num)
            place.location = {'location_address': address}
            place.save(update_fields=['location'])
        except Exception as e:
            logger_writer('SYSTEM', 'error', 'CREATE_DEPARTMENT', f'Create department got error: {str(e)}')
            raise CreatePlaceFailed
        else:
            if company_id:
                if not company:

                    company = Company.objects.filter(pub_id=company_id)
                    if company.exists():
                        company = company.first()
                    else:
                        raise CompanyNotExists
                place.company = company
                place.save(update_fields=['company'])
            return place

    @staticmethod
    def create_company(company_name, department_name_list=None, place_name_list=None):
        if Company.objects.filter(name=company_name).exists():
            raise CompanyAlreadyExists
        else:
            company = Company.objects.create(name=company_name)
            add_tag = AddCompanyTag.objects.create(company=company)
            if not department_name_list:
                department_name_list = [company_name]
            else:
                department_name_list.append(company_name)
            for department_name in department_name_list:
                CompanyServices.create_department(department_name=department_name, company_id=company.id,
                                                  company=company)
            if not place_name_list:
                place_name_list = [company_name]
            else:
                place_name_list.append(company_name)
            for place_name in place_name_list:
                CompanyServices.create_place(place_name=place_name, company_id=company.id, company=company)

            result = AppUserServices.upload_user_qrcode(add_tag.pub_id, 'ADDORG')
            add_tag.qr_code_upload = result
            add_tag.save()

            CompanyDefaultPrint.objects.create(
                company=company,
                place_code={
                    "fst_line": "為防範嚴重特殊傳染性肺炎",
                    "sec_line": "請以通行碼APP掃描此地點做地點紀錄",
                    "last_line": "守護你我健康",
                    "thd_line": "",
                    "forth_line": "～來訪賓客也須配合填寫～"
                })
            return company

    @staticmethod
    def create_user_company(user_id, company_id, department_id, title_id, employed=True, scan_enabled=False):
        app_user = AppUser.objects.filter(pub_id=user_id)
        if not app_user.exists():
            raise UserNotExists
        else:
            app_user = app_user.first()

        company = Company.objects.filter(pub_id=company_id)
        if not company.exists():
            raise CompanyNotExists
        else:
            company = company.first()

        department = Department.objects.filter(pub_id=department_id)
        if not department.exists():
            raise DepartmentNotExists
        else:
            department = department.first()

        title = Title.objects.filter(pub_id=title_id)
        if not title.exists():
            raise TitleNotExists
        else:
            title = title.first()

        if UserCompanyTable.objects.filter(app_user=app_user, company=company, department=department,
                                           title=title, employed=True).exists():
            raise CompanyTitleAlreadyExists
        else:
            UserCompanyTable.objects.create(app_user=app_user, company=company, department=department,
                                            title=title, employed=employed, scan_enabled=scan_enabled)

        if AttendanceStatus.objects.filter(app_user=app_user, company=company).exists():
            raise UserAttendanceStatusAlreadyExists
        else:
            AttendanceStatus.objects.create(app_user=app_user, company=company)
