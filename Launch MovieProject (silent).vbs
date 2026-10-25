' Runs "Launch MovieProject.bat" with no console window.
' The server log goes to server.log; the server stops when its last tab closes.
Option Explicit
Dim fso, sh, dir
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

If Not fso.FileExists(dir & "\.venv\Scripts\python.exe") Then
    MsgBox ".venv not found in:" & vbCrLf & dir & vbCrLf & vbCrLf & _
           "Create it once from a terminal in that folder:" & vbCrLf & vbCrLf & _
           "python -m venv .venv" & vbCrLf & _
           ".venv\Scripts\python -m pip install -r requirements.txt", _
           vbExclamation, "Movie Poster Explorer"
    WScript.Quit 1
End If

sh.CurrentDirectory = dir
sh.Environment("Process")("MP_SILENT") = "1"
sh.Run """" & dir & "\Launch MovieProject.bat""", 0, False
