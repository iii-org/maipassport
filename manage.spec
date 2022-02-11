# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['manage.py'],
             pathex=['/Users/alanyang/maipassport'],
             binaries=[],
             datas=[
                ('envs/.dockernized', 'envs'),
                ('log/system_log.log', 'log'),
                ('config/wsgi.py', 'config'),
                ('maipassport/templates/', 'maipassport/templates/'),
                ('maipassport/citadel/templatetags/', 'maipassport/citadel/templatetags/'),
                ('staticfiles/', 'staticfiles/'),
             ],
             hiddenimports=[
                "maipassport.transfers.context_processors",
                "django_db_logger.templatetags",
                "maipassport.companies.context_processors",
                "django.contrib.sites.templatetags",
                "maipassport.contracts.templatetags",
                "memoize.templatetags",
                "qrcode.templatetags",
                "django.contrib.admin.context_processors",
                "django.contrib.sessions.templatetags",
                "maipassport.taskapp.celery.CeleryAppConfig.context_processors",
                "django.contrib.staticfiles.context_processors",
                "maipassport.contracts.context_processors",
                "django.contrib.auth.templatetags",
                "maipassport.core.context_processors",
                "qrcode.context_processors",
                "django.contrib.sites.context_processors",
                "maipassport.citadel.context_processors",
                "storages.templatetags",
                "maipassport.taskapp.celery.CeleryAppConfig.templatetags",
                "maipassport.users.context_processors",
                "django_extensions.context_processors",
                "maipassport.records.context_processors",
                "django.contrib.sessions.context_processors",
                "maipassport.transfers.templatetags",
                "maipassport.core.templatetags",
                "rest_framework.context_processors",
                "django_db_logger.context_processors",
                "storages.context_processors",
                "django.contrib.messages.templatetags",
                "maipassport.records.templatetags",
                "maipassport.taskapp.celery.CeleryAppConfig",
                "django.contrib.contenttypes.context_processors",
                "memoize.context_processors",
                "maipassport.users.templatetags",
                "django.contrib.contenttypes.templatetags",
                "maipassport.companies.templatetags",
                "celery.fixups",
                "celery.fixups.django",
                "celery.loaders.app",
                "qinspect",
                "qinspect.middleware",
                "django_redis",
                "django_redis.cache",
                "django_redis.client",
                "django_redis.serializers",
                "django_redis.serializers.pickle",
                "django_redis.compressors",
                "django_redis.compressors.identity",
                "django.contrib.auth.hashers.Argon2PasswordHasher",
                "django.contrib.auth.hashers.PBKDF2PasswordHasher",
                "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
                "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
                "django.contrib.auth.hashers.BCryptPasswordHasher",
                "argon2"
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)


##### include mydir in distribution #######
def extra_datas(mydir):
    def rec_glob(p, files):
        import os
        import glob
        for d in glob.glob(p):
            if os.path.isfile(d):
                files.append(d)
            rec_glob("%s/*" % d, files)
    files = []
    rec_glob("%s/*" % mydir, files)
    extra_datas = []
    for f in files:
        extra_datas.append((f, f, 'DATA'))
    return extra_datas
a.datas += extra_datas('maipassport')
###########################################

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='manage',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='manage')
