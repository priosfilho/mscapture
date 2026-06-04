Option Explicit

Dim shell, fso, folder, script, cmd, launched
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

folder = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(folder, "ms_capture_v4.py")

If Not fso.FileExists(script) Then
    MsgBox "Não encontrei o arquivo ms_capture_v4.py na mesma pasta deste lançador." & vbCrLf & _
           "Mantenha todos os arquivos extraídos na mesma pasta.", vbCritical, "ms_capture"
    WScript.Quit 1
End If

launched = False

' 1) Preferência: pyw, que abre interface gráfica sem janela de console.
On Error Resume Next
cmd = "pyw -3 " & Quote(script) & " --gui"
shell.Run cmd, 0, False
If Err.Number = 0 Then launched = True
Err.Clear
On Error GoTo 0

' 2) Fallback: pythonw, também sem console.
If Not launched Then
    On Error Resume Next
    cmd = "pythonw " & Quote(script) & " --gui"
    shell.Run cmd, 0, False
    If Err.Number = 0 Then launched = True
    Err.Clear
    On Error GoTo 0
End If

If Not launched Then
    MsgBox "Não consegui iniciar o Python em modo gráfico." & vbCrLf & vbCrLf & _
           "Tente abrir o arquivo ABRIR_ms_capture_COM_DIAGNOSTICO.bat para ver a mensagem de erro." & vbCrLf & _
           "Confirme também se o Python 3 está instalado com tkinter.", vbCritical, "ms_capture"
    WScript.Quit 1
End If

Function Quote(ByVal s)
    Quote = Chr(34) & s & Chr(34)
End Function
