; Instalador de Chloe POS (Inno Setup 6)
; No se compila a mano: lo ejecuta construir.py, que define AppVersion y BuildDir.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef BuildDir
  #define BuildDir "build\programa"
#endif

[Setup]
; El AppId identifica al programa: NO cambiarlo nunca, así cada versión nueva se instala encima de la anterior
AppId={{D9BD1FE3-3DD3-4774-A0F2-3CBA2441E172}
AppName=Chloe POS
AppVersion={#AppVersion}
AppVerName=Chloe POS {#AppVersion}
AppPublisher=Chloe Creaciones
VersionInfoVersion={#AppVersion}
; Instalación en la cuenta del usuario: no pide permisos de administrador (ni al instalar ni al actualizar)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Chloe POS
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
OutputDir=salida
OutputBaseFilename=ChloePOS-Setup-{#AppVersion}
SetupIconFile=chloe.ico
UninstallDisplayIcon={app}\chloe.ico
UninstallDisplayName=Chloe POS
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un ícono en el escritorio"; GroupDescription: "Accesos directos:"

[InstallDelete]
; Al actualizar se reemplaza el programa completo. Los datos (base de datos y respaldos) están en otras carpetas y no se tocan.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"

[Dirs]
Name: "{userdocs}\Chloe POS - Respaldos"; Flags: uninsneveruninstall

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Chloe POS"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"""; WorkingDir: "{app}"; IconFilename: "{app}\chloe.ico"; Tasks: escritorio
Name: "{autoprograms}\Chloe POS\Chloe POS"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"""; WorkingDir: "{app}"; IconFilename: "{app}\chloe.ico"
Name: "{autoprograms}\Chloe POS\Respaldar base de datos"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"" --respaldar"; WorkingDir: "{app}"; IconFilename: "{app}\chloe.ico"
Name: "{autoprograms}\Chloe POS\Carpeta de respaldos"; Filename: "{userdocs}\Chloe POS - Respaldos"
Name: "{autoprograms}\Chloe POS\Detener Chloe POS"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"" --detener"; WorkingDir: "{app}"; IconFilename: "{app}\chloe.ico"
Name: "{autoprograms}\Chloe POS\Desinstalar Chloe POS"; Filename: "{uninstallexe}"

[Run]
; Instalación normal: casilla "Abrir Chloe POS" al terminar
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"""; WorkingDir: "{app}"; Description: "Abrir Chloe POS"; Flags: postinstall nowait skipifsilent
; Actualización desde el programa (instalación silenciosa): solo vuelve a levantar el servidor;
; la ventana que ya estaba abierta se recarga sola
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"" --servidor"; WorkingDir: "{app}"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"" --detener"; Flags: runhidden waituntilterminated; RunOnceId: "DetenerServidor"

[Code]
// Antes de copiar archivos, detiene el programa si está abierto (para poder reemplazarlo)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  if FileExists(ExpandConstant('{app}\python\pythonw.exe')) then
    Exec(ExpandConstant('{app}\python\pythonw.exe'), '"' + ExpandConstant('{app}\lanzador.py') + '" --detener',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(800);
  Result := '';
end;
