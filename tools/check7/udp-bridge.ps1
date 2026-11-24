param(
    [Parameter(Mandatory=$true)][string]$LocalUbuntuIP,
    [Parameter(Mandatory=$true)][int]$LocalPort,
    [Parameter(Mandatory=$true)][int]$ListenPort,
    [Parameter(Mandatory=$true)][string]$PeerIP,
    [Parameter(Mandatory=$true)][int]$PeerPort
)

$ErrorActionPreference = 'Stop'
$localAddress = [System.Net.IPAddress]::Parse($LocalUbuntuIP)
$peerAddress = [System.Net.IPAddress]::Parse($PeerIP)
if ($localAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $peerAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
    throw 'IPv4 addresses are required.'
}
foreach ($number in @($LocalPort, $ListenPort, $PeerPort)) {
    if ($number -lt 1 -or $number -gt 65535) { throw 'Ports must be in 1..65535.' }
}
if ($LocalUbuntuIP -eq $PeerIP -and $LocalPort -eq $PeerPort) {
    throw 'The two endpoints must be different.'
}

$udp = [System.Net.Sockets.UdpClient]::new($ListenPort)
$udp.Client.ReceiveTimeout = 1000
$localTarget = [System.Net.IPEndPoint]::new($localAddress, $LocalPort)
$peerTarget = [System.Net.IPEndPoint]::new($peerAddress, $PeerPort)
$sentLocal = 0
$sentPeer = 0
Write-Output "READY UDP :$ListenPort Ubuntu=$localTarget peer=$peerTarget (Ctrl+C to stop)"
try {
    while ($true) {
        $source = [System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, 0)
        try { $payload = $udp.Receive([ref]$source) }
        catch [System.Net.Sockets.SocketException] {
            if ($_.Exception.SocketErrorCode -eq [System.Net.Sockets.SocketError]::TimedOut) { continue }
            throw
        }
        if ($source.Address.Equals($localAddress) -and $source.Port -eq $LocalPort) {
            [void]$udp.Send($payload, $payload.Length, $peerTarget)
            $sentPeer++
        } elseif ($source.Address.Equals($peerAddress) -and $source.Port -eq $PeerPort) {
            [void]$udp.Send($payload, $payload.Length, $localTarget)
            $sentLocal++
        } else {
            Write-Output "IGNORED unexpected sender $source"
            continue
        }
        if (($sentPeer + $sentLocal) -le 4 -or ($sentPeer + $sentLocal) % 500 -eq 0) {
            Write-Output "FORWARDED to-peer=$sentPeer to-Ubuntu=$sentLocal"
        }
    }
} finally {
    $udp.Dispose()
    Write-Output "STOPPED to-peer=$sentPeer to-Ubuntu=$sentLocal"
}
