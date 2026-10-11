/* ========================================================================== 
 * びっくらポン 外枠系 3Dプリント用
 * ========================================================================== 
 *
 * 外枠を構成する部品だけを開くためのファイル。
 * OUTER_PARTを切り替え、部品ごとにSTLへ書き出す。
 *
 * housing       : 円形内壁を持つ外枠本体
 * front_plate   : モーター取付側の前面板
 * rear_plate    : 回転軸を支える後面板
 * hopper_adapter: 上側のカプセル投入口
 * outlet_adapter: 下側の排出口
 * ========================================================================== */

OUTER_PART = "housing";
// "housing" / "front_plate" / "rear_plate" /
// "hopper_adapter" / "outlet_adapter"

PRINT_PART = OUTER_PART;
include <capsule_dispenser.scad>
