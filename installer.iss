[Setup]
AppId={{7D3B5C2E-4F1A-4B8E-9C6D-2A5E8F1B3C47}
AppName=내 사진 뷰어
AppVersion=1.0
AppPublisher=내 사진 뷰어
DefaultDirName={autopf}\내 사진 뷰어
DefaultGroupName=내 사진 뷰어
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=내사진뷰어_설치
SetupIconFile=app.ico
UninstallDisplayIcon={app}\내사진뷰어.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; Flags: unchecked
Name: "assoc"; Description: "모든 사진 파일(JPG, PNG, BMP, GIF, WebP, TIFF 등)을 이 프로그램으로 열기"

[Files]
Source: "dist\내사진뷰어\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\내 사진 뷰어"; Filename: "{app}\내사진뷰어.exe"
Name: "{group}\내 사진 뷰어 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\내 사진 뷰어"; Filename: "{app}\내사진뷰어.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\내사진뷰어.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\내사진뷰어.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\내사진뷰어.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "내 사진 뷰어"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\MyPhotoViewer.Image"; ValueType: string; ValueName: ""; ValueData: "이미지 파일"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\MyPhotoViewer.Image\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\내사진뷰어.exe,0"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\MyPhotoViewer.Image\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\내사진뷰어.exe"" ""%1"""; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "내 사진 뷰어"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "사진 보기와 AI 편집 도구"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "MyPhotoViewer"; ValueData: "Software\MyPhotoViewer\Capabilities"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".jpg"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.jpg\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".jpeg"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.jpeg\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".jpe"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.jpe\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".jfif"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.jfif\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".png"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.png\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".bmp"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.bmp\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".gif"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.gif\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webp"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.webp\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".tif"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.tif\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".tiff"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.tiff\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\MyPhotoViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ico"; ValueData: "MyPhotoViewer.Image"; Flags:; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.ico\OpenWithProgids"; ValueType: string; ValueName: "MyPhotoViewer.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc

[Run]
Filename: "ms-settings:defaultapps"; Description: "기본 앱 설정 열기 (사진 보기 앱을 '내 사진 뷰어'로 선택)"; Flags: shellexec postinstall skipifsilent; Tasks: assoc
Filename: "{app}\내사진뷰어.exe"; Description: "내 사진 뷰어 실행"; Flags: nowait postinstall skipifsilent unchecked
