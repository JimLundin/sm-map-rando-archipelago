set -e
ASAR=/home/jim/smmr/tools/bin/asar
ROOT=$(pwd)
sub=romhacks/maprando
mkdir -p build/$sub
python3 resources/create_dummies.py build/00.sfc build/ff.sfc
cd $ROOT/$sub
$ASAR --no-title-check --symbols=wla --symbols-path=$ROOT/build/$sub/multiworld.sym main.asm $ROOT/build/00.sfc
$ASAR --no-title-check --symbols=wla --symbols-path=$ROOT/build/$sub/multiworld.sym main.asm $ROOT/build/ff.sfc
cd $ROOT
python3 resources/create_ips.py build/00.sfc build/ff.sfc build/$sub/multiworld-basepatch.ips
python3 resources/sym2json.py build/$sub/multiworld.sym common/*.asm > build/$sub/sm-basepatch-symbols.json
rm build/00.sfc build/ff.sfc
