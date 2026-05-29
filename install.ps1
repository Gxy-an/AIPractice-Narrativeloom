# 使用国内 PyPI 镜像安装依赖，规避访问 pypi.org 时的 SSL 中断等问题。
# 用法：在仓库根目录执行  .\install.ps1
# 若仍失败，可编辑下方 $IndexUrl 为阿里云等其它镜像。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# 清华镜像（可改为 https://mirrors.aliyun.com/pypi/simple/ ）
$IndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
$Trusted = @(
    "pypi.tuna.tsinghua.edu.cn",
    "mirrors.aliyun.com",
    "pypi.org",
    "files.pythonhosted.org"
)

$trustedArgs = [System.Collections.ArrayList]@()
foreach ($h in $Trusted) {
    [void]$trustedArgs.Add("--trusted-host")
    [void]$trustedArgs.Add($h)
}
Write-Host "Using index: $IndexUrl" -ForegroundColor Cyan

& py -3 -m pip install @trustedArgs -i $IndexUrl --upgrade pip
& py -3 -m pip install @trustedArgs -i $IndexUrl -r requirements.txt

Write-Host "Done. Run: py -3 -m streamlit run app.py" -ForegroundColor Green
