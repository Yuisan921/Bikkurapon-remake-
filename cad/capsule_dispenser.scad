/* ==========================================================================
 * びっくらポン カプセルディスペンサー(回転ゲート式、OpenSCADパラメトリック)
 * ==========================================================================
 * OpenSCAD (https://openscad.org/、無料) で開いてください。
 *
 * 【機構の考え方】
 *   ホッパー(カプセルをまとめて入れる漏斗)の一番下は「カプセル1個分の
 *   のど」になっていて、常に1個だけ待機している。その真下に、カプセル
 *   1個分の穴(ポケット)を1つだけ空けた円盤(ゲートディスク)があり、
 *   サーボの軸に固定されている。普段はポケットが「のど」からズレた
 *   位置にあり、円盤の面がフタになってカプセルを止めている。
 *   サーボが90度回転すると、ポケットが「のど」の真下を通過する瞬間に
 *   カプセルが1個だけハマって一緒に運ばれ、反対側の排出口の真下に
 *   来たところで下に落ちる。サーボが元の角度に戻れば、また塞がれる。
 *
 *   この機構を「当たり用ホッパー」「はずれ用(弱景品)ホッパー」として
 *   2セット作れば、抽選結果に応じてどちらか一方のサーボだけを動かす
 *   だけで、必ず対応する景品のカプセルが出てくる構成になる。
 *
 * 【使い方】
 *   1. 下の PART 変数を "hopper" / "gate_disc" / "base" のいずれかにして
 *      OpenSCADで開き、File > Export > Export as STL でパーツごとに
 *      出力する(1セットにつき hopper x1, gate_disc x1, base x1)
 *   2. 当たり用・はずれ用でそれぞれ同じものを1セットずつ、計2セット印刷する
 *   3. PART を "assembly" にすると組み立てイメージをプレビューできる
 *      (プレビュー用途のみ。これ自体はSTL出力しない)
 *
 * 【組み立て】
 *   base(下) → gate_disc(中、サーボホーンで軸に固定) → hopper(上) の順に
 *   重ね、hopperとbaseの4隅をネジ止めしてgate_discを挟み込む。
 *   サーボ本体はbaseの下にできるポケット(servo_pocket)に差し込み、
 *   出力軸をbase中心の穴からgate_disc裏側のホーン受けに固定する。
 *
 * 【注意】
 *   各寸法は目安です。カプセルとサーボは個体差があるので、印刷前に
 *   実物をノギスで測って capsule_diameter や servo_* を調整してください。
 *   特に servo_shaft_offset_x はサーボの型番・メーカーでばらつきが大きい
 *   ので、必ず実測して合わせてください。
 * ========================================================================== */

// ---- 出力/プレビューするものを選ぶ ----
PART = "assembly"; // "hopper" / "gate_disc" / "base" / "assembly"

// ---- 基本パラメータ ----
capsule_diameter = 45;   // カプセル直径(mm)。実測して調整
print_clearance  = 0.6;  // 可動部同士のすき間(mm)

// ---- ゲートディスク(回転部分)----
pocket_clearance    = 4;                                    // カプセルとポケット穴のすき間
pocket_diameter     = capsule_diameter + pocket_clearance;  // ポケット穴の直径
disc_thickness      = 8;                                    // ディスクの厚み
hub_radius          = 9;                                    // 中心軸まわりの厚肉部半径
hole_center_radius  = pocket_diameter/2 + hub_radius + 3;   // 中心〜ポケット中心の距離(R)
disc_radius         = hole_center_radius + pocket_diameter/2 + 6; // ディスク外径

// ---- サーボ(MG90S系、9gサーボ標準サイズ。実測推奨)----
servo_body_w        = 12.2;  // 本体幅
servo_body_l        = 23.0;  // 本体奥行き(フランジ含まず)
servo_body_h        = 22.8;  // 本体高さ(フランジ位置まで)
servo_shaft_offset_x = 7.8;  // 出力軸中心が本体端(奥行き方向)から何mmか ※要実測
servo_horn_boss_d   = 10;    // サーボホーンの受け穴径(目安、実物に合わせて調整)
servo_horn_screw_d  = 2.2;   // ホーン固定ネジ穴径

// ---- ホッパー(カプセル投入部)----
hopper_capacity_h    = 90;                     // ホッパー本体(漏斗部分)の高さ
hopper_top_diameter  = 110;                    // ホッパー上部の開口径
throat_diameter      = capsule_diameter + 3;   // カプセルが1列に並ぶ「のど」の径
throat_height        = capsule_diameter * 1.6; // のど部分の高さ(カプセル1〜2個分)
top_plate_thickness  = 4;                      // ホッパー下端の固定板の厚み

// ---- ベース(固定土台)----
base_thickness = 4;
chute_length   = 40;                    // 排出口から外に伸ばすシュートの長さ
chute_width    = pocket_diameter + 6;   // シュートの幅(排出口の穴より少し広め)
mount_hole_r   = 1.8; // hopperとbaseを止めるネジの下穴半径(M3タッピング目安)

$fn = 96;

// ==========================================================================
// パーツ: ゲートディスク
// ==========================================================================
module gate_disc() {
    difference() {
        cylinder(r = disc_radius, h = disc_thickness);

        // ポケット穴(カプセル1個分。角度0度=「のど」の位置に合わせてある)
        translate([hole_center_radius, 0, -1])
            cylinder(r = pocket_diameter/2, h = disc_thickness + 2);

        // 中心のサーボホーン受け
        translate([0, 0, -1])
            cylinder(r = servo_horn_boss_d/2, h = disc_thickness + 2);

        // ホーン固定ネジ穴(対角2箇所。実物のホーンに合わせて位置調整すること)
        for (a = [0, 180])
            rotate([0, 0, a])
                translate([servo_horn_boss_d/2 + 3, 0, -1])
                    cylinder(r = servo_horn_screw_d/2, h = disc_thickness + 2);
    }
}

// ==========================================================================
// パーツ: ホッパー(上部固定板 + カプセル投入用の漏斗)
// ==========================================================================
module hopper() {
    difference() {
        union() {
            // 下端の固定板(baseとネジ止めしてgate_discを挟み込む)
            cylinder(r = disc_radius + 10, h = top_plate_thickness);

            // カプセルが1個ずつ並ぶ「のど」(ポケット穴の真上に配置)
            translate([hole_center_radius, 0, 0])
                cylinder(d = throat_diameter, h = throat_height + top_plate_thickness);

            // すり鉢状のホッパー本体(のどの上に乗る)
            translate([hole_center_radius, 0, throat_height + top_plate_thickness - 0.1])
                cylinder(d1 = throat_diameter, d2 = hopper_top_diameter, h = hopper_capacity_h);
        }

        // 「のど」の真下、固定板を貫通させてgate_discのポケットに繋げる
        translate([hole_center_radius, 0, -1])
            cylinder(d = pocket_diameter, h = top_plate_thickness + 2);

        // 中心の軸穴(サーボホーンが通る、gate_discと干渉しないための逃げ)
        translate([0, 0, -1])
            cylinder(r = servo_horn_boss_d/2 + print_clearance, h = top_plate_thickness + 2);

        // 取付ネジ穴(4隅、baseと共通位置)
        for (a = [45, 135, 225, 315])
            rotate([0, 0, a])
                translate([disc_radius + 4, 0, -1])
                    cylinder(r = mount_hole_r, h = top_plate_thickness + 2);
    }
}

// ==========================================================================
// パーツ: ベース(下部固定板 + 排出シュート + サーボポケット)
// ==========================================================================
module base_plate() {
    difference() {
        union() {
            cylinder(r = disc_radius + 10, h = base_thickness);

            // 排出口(角度90度の位置)から前方(-X方向)に伸びるシュート
            // 幅は排出口の穴よりわずかに広くしておく(穴の円と壁が1点で
            // 接する状態になると数値誤差で非2-manifold形状になるため)
            rotate([0, 0, 90])
                translate([hole_center_radius - chute_width/2, -chute_width/2, 0])
                    cube([chute_width, chute_length, base_thickness + 6]);
        }

        // 排出口の穴(角度90度の位置。ポケット穴と同径)
        rotate([0, 0, 90])
            translate([hole_center_radius, 0, -1])
                cylinder(d = pocket_diameter, h = base_thickness + 8);

        // 中心の軸穴(サーボの出力軸+ホーンが通る)
        translate([0, 0, -1])
            cylinder(r = servo_horn_boss_d/2 + print_clearance, h = base_thickness + 2);

        // 取付ネジ穴(4隅、hopperと共通位置)
        for (a = [45, 135, 225, 315])
            rotate([0, 0, a])
                translate([disc_radius + 4, 0, -1])
                    cylinder(r = mount_hole_r, h = base_thickness + 2);
    }

    // サーボを差し込むポケット(ベース裏側に垂れ下がる、底なしの筒)
    // 出力軸が中心の軸穴(0,0)の真下に来るように servo_shaft_offset_x で調整
    translate([-servo_shaft_offset_x, -servo_body_w/2 - print_clearance, -servo_body_h])
        servo_pocket();
}

module servo_pocket() {
    wall = 2;
    // ベース本体とちょうど面一(ぴったり同じ高さ)で接すると、数値誤差で
    // 非2-manifold(印刷不可な形状)になることがあるため、上端を少しだけ
    // ベース側へめり込ませて確実に重なるようにする
    overlap = 0.5;
    pocket_l = servo_body_l + print_clearance*2;
    pocket_w = servo_body_w + print_clearance*2;
    difference() {
        // 外側の筒(壁厚wall、底なし、上端はoverlap分だけ余分に高い)
        translate([-wall, -wall, 0])
            cube([pocket_l + wall*2, pocket_w + wall*2, servo_body_h + overlap]);
        // 内側のサーボ差し込みスペース(底なし=下に貫通)
        translate([0, 0, -1])
            cube([pocket_l, pocket_w, servo_body_h + overlap + 2]);
        // 配線を通す切り欠き(奥側の壁に1箇所)
        translate([pocket_l/2 - 4, pocket_w + wall - 0.1, servo_body_h - 8])
            cube([8, wall + 0.2, 8]);
    }
}

// ==========================================================================
// 組み立てプレビュー(確認用。STL出力はhopper/gate_disc/baseを個別に)
// ==========================================================================
module assembly_preview() {
    color("SlateGray") base_plate();
    translate([0, 0, base_thickness + print_clearance])
        color("Gold") gate_disc();
    translate([0, 0, base_thickness + disc_thickness + print_clearance*2])
        color("LightBlue", 0.5) hopper();
}

if (PART == "hopper") hopper();
else if (PART == "gate_disc") gate_disc();
else if (PART == "base") base_plate();
else assembly_preview();
