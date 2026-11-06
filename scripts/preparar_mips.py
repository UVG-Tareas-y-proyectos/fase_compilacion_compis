"""Descargar MARS oficial y, si hace falta, un JRE portátil en tools/."""

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MARS_URL='https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar'
MARS_SHA256='ac340b676ba2b62246b9df77e62f81ad4447bcfd329ab539716bcd09950b7096'


def download(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Compiscript-UVG'})
    with urllib.request.urlopen(request,timeout=120) as response:
        return response.read()


def checked_download(url,checksum,target):
    data=download(url)
    if hashlib.sha256(data).hexdigest()!=checksum:
        raise RuntimeError('la descarga no coincide con su SHA-256')
    target.write_bytes(data)


def main():
    tools=ROOT/'tools'
    tools.mkdir(exist_ok=True)
    jar=tools/'Mars4_5.jar'
    if not jar.exists() or hashlib.sha256(jar.read_bytes()).hexdigest()!=MARS_SHA256:
        print('Descargando MARS 4.5 del repositorio oficial...')
        checked_download(MARS_URL,MARS_SHA256,jar)
    executable='java.exe' if os.name=='nt' else 'java'
    if not shutil.which('java') and not (tools/'jre/bin'/executable).exists():
        systems={'Windows':'windows','Linux':'linux','Darwin':'mac'}
        system=systems[platform.system()]
        architecture='aarch64' if platform.machine().lower() in {'arm64','aarch64'} else 'x64'
        url=f'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture={architecture}&image_type=jre&os={system}&vendor=eclipse'
        package=json.loads(download(url))[0]['binary']['package']
        print('Descargando Eclipse Temurin JRE 17 portátil...')
        archive=tools/package['name']
        checked_download(package['link'],package['checksum'],archive)
        extracted=tools/'java_descarga'
        extracted.mkdir(exist_ok=True)
        if archive.suffix=='.zip':
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    if extracted.resolve() not in (extracted/name).resolve().parents:
                        raise RuntimeError('ruta insegura en el archivo Java')
                z.extractall(extracted)
        else:
            with tarfile.open(archive) as t:
                members=[]
                for member in t.getmembers():
                    if extracted.resolve() not in (extracted/member.name).resolve().parents:
                        raise RuntimeError('ruta insegura en el archivo Java')
                    if member.isfile() or member.isdir():
                        members.append(member)
                t.extractall(extracted,members=members)
        source=next(p for p in extracted.iterdir() if p.is_dir())
        if system=='mac':
            source=source/'Contents/Home'
        source.rename(tools/'jre')
        archive.unlink()
    print('MARS preparado. Puede ejecutar el compilador y las pruebas MIPS.')


if __name__=='__main__':
    main()
