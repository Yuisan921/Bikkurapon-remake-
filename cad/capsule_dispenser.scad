/* ==========================================================================
 * びっくらポン 縦型180度ローター式カプセルディスペンサー
 * ==========================================================================
 *
 * 上下180度対向のU字ポケットを2個持つ。上側のポケットへカプセルを
 * 1個だけ入れ、ローターを180度回すと下側から排出される。同時に、空の
 * 反対側ポケットが上へ移動して次の1個を装填する。サーボは毎回戻さず、
 * 0度と180度を交互に切り替える。
 *
 * 座標系（assembly表示時）:
 *   X = 左右、Y = 前後（ローター軸）、Z = 上下
 *
 * 1ホッパーにつき次の部品を各1個印刷する:
 *   rotor / housing / front_plate / rear_plate /
 *   hopper_adapter / outlet_adapter
 *
 * 前後プレートとhousingはM4通しボルト4本で固定する。ローター前面は
 * サーボホーンへ固定し、後面の軸をrear_plateで支持する。サーボ本体は
 * 市販の金属ブラケットなどでfront_plateまたは筐体へ固定する。
 * ========================================================================== */

// ---- 出力する部品 ----
PART = "assembly";
// "rotor" / "housing" / "front_plate" / "rear_plate" /
// "hopper_adapter" / "outlet_adapter" / "assembly"

// assembly表示時のローター位置。0と180のどちらも装填／排出位置になる。
ROTOR_PREVIEW_ANGLE = 0;

// ---- カプセル ----
// 一般的な小型ガチャカプセルを想定した既定値。必ず現物を実測すること。
// 45/48/50/65mmなどへ変更すれば、周辺寸法も追従する。
capsule_diameter = 48;

// カプセルとポケット／通路の直径方向の余裕。
pocket_clearance = 3.0;
throat_clearance = 3.5;

// ---- ローター ----
pocket_diameter = capsule_diameter + pocket_clearance;
rotor_thickness = capsule_diameter + 4;
hub_radius = 12;
pocket_center_radius = pocket_diameter/2 + hub_radius + 4;
rotor_rim = 6;
rotor_radius = pocket_center_radius + pocket_diameter/2 + rotor_rim;

// ローターとケースのクリアランス。造形精度に合わせて0.6〜1.0mm程度で調整。
radial_clearance = 0.8;
axial_clearance = 0.7;

// 後面の支持軸。rear_plateの穴へ入り、サーボ軸だけに荷重が集中するのを防ぐ。
rear_pivot_diameter = 10;
rear_pivot_clearance = 0.6;

// サーボホーン固定用の目安寸法。使用するホーンに合わせて調整すること。
horn_access_diameter = 28;
horn_center_hole_diameter = 3.2;
horn_mount_hole_diameter = 2.2;
horn_mount_hole_spacing = 14;
horn_pilot_depth = 8;

// ---- ケース／プレート ----
housing_wall = 7;
housing_depth = rotor_thickness + axial_clearance*2;
housing_width = (rotor_radius + housing_wall) * 2;
housing_height = housing_width;
throat_diameter = capsule_diameter + throat_clearance;

front_plate_thickness = 4;
rear_plate_thickness = 4;
case_bolt_diameter = 4.4;   // M4通しボルト用
case_bolt_edge = 9;

// ホッパー／排出口アダプター
adapter_flange_width = 90;
adapter_flange_depth = housing_depth;
adapter_flange_thickness = 4;
adapter_wall = 3.5;
hopper_neck_height = 32;
outlet_neck_height = 20;
adapter_bolt_diameter = 3.4; // M3用
adapter_bolt_x = 34;
adapter_bolt_y = housing_depth/2 - 7;

$fn = 120;

// ==========================================================================
// 共通ヘルパー
// ==========================================================================

module cylinder_y(d, h) {
    rotate([90, 0, 0]) cylinder(d=d, h=h, center=true);
}

module case_bolt_pattern(depth) {
    for (x = [-housing_width/2 + case_bolt_edge,
              housing_width/2 - case_bolt_edge])
        for (z = [-housing_height/2 + case_bolt_edge,
                  housing_height/2 - case_bolt_edge])
            translate([x, 0, z]) cylinder_y(case_bolt_diameter, depth);
}

module adapter_bolt_pattern(height) {
    for (x = [-adapter_bolt_x, adapter_bolt_x])
        for (y = [-adapter_bolt_y, adapter_bolt_y])
            translate([x, y, -1])
                cylinder(d=adapter_bolt_diameter, h=height + 2);
}

// ==========================================================================
// ローター
// ==========================================================================

module rotor_mechanical() {
    rear_pivot_length = axial_clearance + rear_plate_thickness + 1.5;

    difference() {
        union() {
            // 回転体本体。スライサーのインフィルを低めにして軽量化できる。
            cylinder_y(rotor_radius*2, rotor_thickness);

            // 後面支持軸
            translate([0, rotor_thickness/2 + rear_pivot_length/2, 0])
                cylinder_y(rear_pivot_diameter, rear_pivot_length);
        }

        // 180度対向の2ポケット。片方が下で排出すると、反対側が上で
        // 次のカプセルを受ける。回転中はhousing内壁がU字の口を塞ぐ。
        for (angle = [0, 180])
            rotate([0, angle, 0]) {
                translate([0, 0, pocket_center_radius])
                    cylinder_y(pocket_diameter, rotor_thickness + 4);

                translate([
                    -pocket_diameter/2,
                    -(rotor_thickness + 4)/2,
                    pocket_center_radius
                ])
                    cube([
                        pocket_diameter,
                        rotor_thickness + 4,
                        rotor_radius - pocket_center_radius + 3
                    ]);
            }

        // サーボホーン中央ネジの下穴（前面からのみ）
        translate([0, -rotor_thickness/2 + horn_pilot_depth/2 - 0.2, 0])
            cylinder_y(horn_center_hole_diameter, horn_pilot_depth + 0.4);

        // 汎用ホーン固定用の2本の下穴
        for (x = [-horn_mount_hole_spacing/2, horn_mount_hole_spacing/2])
            translate([x, -rotor_thickness/2 + horn_pilot_depth/2 - 0.2, 0])
                cylinder_y(horn_mount_hole_diameter, horn_pilot_depth + 0.4);
    }
}

// ==========================================================================
// ローター外周ケース
// ==========================================================================

module housing_mechanical() {
    top_channel_z = rotor_radius - 2;
    channel_height = housing_height/2 - top_channel_z + 4;

    difference() {
        cube([housing_width, housing_depth, housing_height], center=true);

        // ローターが回る円形空間
        cylinder_y(
            rotor_radius*2 + radial_clearance*2,
            housing_depth + 2
        );

        // 上下のカプセル通路。housingを広い面を下にして印刷したときに
        // 50mm超のブリッジが発生しないよう、前後へ貫通する角形スロットにする。
        // 組み立て後はfront/rear_plateが前後を塞ぎ、単列通路になる。
        translate([
            -throat_diameter/2,
            -(housing_depth + 2)/2,
            top_channel_z
        ])
            cube([
                throat_diameter,
                housing_depth + 2,
                channel_height
            ]);

        translate([
            -throat_diameter/2,
            -(housing_depth + 2)/2,
            -housing_height/2 - 2
        ])
            cube([
                throat_diameter,
                housing_depth + 2,
                channel_height
            ]);

        // 前後プレート固定用M4通し穴
        case_bolt_pattern(housing_depth + 4);

        // 上面・下面アダプター固定用M3穴
        for (x = [-adapter_bolt_x, adapter_bolt_x])
            for (y = [-adapter_bolt_y, adapter_bolt_y]) {
                translate([x, y, rotor_radius - 2])
                    cylinder(d=adapter_bolt_diameter,
                             h=housing_height/2 - rotor_radius + 4);
                translate([x, y, -housing_height/2 - 2])
                    cylinder(d=adapter_bolt_diameter,
                             h=housing_height/2 - rotor_radius + 4);
            }
    }
}

// ==========================================================================
// 前後プレート
// ==========================================================================

module front_plate_mechanical() {
    difference() {
        cube([
            housing_width,
            front_plate_thickness,
            housing_height
        ], center=true);

        // サーボホーンとローター前面へアクセスする穴
        cylinder_y(horn_access_diameter, front_plate_thickness + 2);
        case_bolt_pattern(front_plate_thickness + 2);
    }
}

module rear_plate_mechanical() {
    difference() {
        cube([
            housing_width,
            rear_plate_thickness,
            housing_height
        ], center=true);

        // ローター後面支持軸用の穴
        cylinder_y(
            rear_pivot_diameter + rear_pivot_clearance,
            rear_plate_thickness + 2
        );
        case_bolt_pattern(rear_plate_thickness + 2);
    }
}

// ==========================================================================
// ホッパー／排出口アダプター
// ==========================================================================

module adapter(neck_height) {
    neck_outer_diameter = throat_diameter + adapter_wall*2;

    difference() {
        union() {
            cube([
                adapter_flange_width,
                adapter_flange_depth,
                adapter_flange_thickness
            ]);

            translate([
                adapter_flange_width/2,
                adapter_flange_depth/2,
                adapter_flange_thickness
            ])
                cylinder(d=neck_outer_diameter, h=neck_height);
        }

        translate([
            adapter_flange_width/2,
            adapter_flange_depth/2,
            -1
        ])
            cylinder(
                d=throat_diameter,
                h=adapter_flange_thickness + neck_height + 2
            );

        translate([
            adapter_flange_width/2,
            adapter_flange_depth/2,
            0
        ])
            adapter_bolt_pattern(adapter_flange_thickness);
    }
}

module hopper_adapter() {
    adapter(hopper_neck_height);
}

module outlet_adapter() {
    adapter(outlet_neck_height);
}

// ==========================================================================
// 組み立てプレビュー
// ==========================================================================

module assembly_preview() {
    front_y = -(housing_depth/2 + front_plate_thickness/2);
    rear_y = housing_depth/2 + rear_plate_thickness/2;

    color("DimGray") housing_mechanical();

    rotate([0, ROTOR_PREVIEW_ANGLE, 0])
        color("Orange") rotor_mechanical();

    translate([0, front_y, 0])
        color("LightSteelBlue", 0.55) front_plate_mechanical();

    translate([0, rear_y, 0])
        color("LightSteelBlue", 0.55) rear_plate_mechanical();

    translate([
        -adapter_flange_width/2,
        -adapter_flange_depth/2,
        housing_height/2
    ])
        color("PaleGreen", 0.75) hopper_adapter();

    translate([
        adapter_flange_width/2,
        -adapter_flange_depth/2,
        -housing_height/2
    ])
        rotate([0, 180, 0])
            color("Khaki", 0.75) outlet_adapter();
}

// ==========================================================================
// 印刷向け配置
// ==========================================================================

echo(str("カプセル直径: ", capsule_diameter, " mm"));
echo(str("ローター: 直径 ", rotor_radius*2,
         " x 厚さ ", rotor_thickness, " mm"));
echo(str("ケース: ", housing_width, " x ", housing_height,
         " x 奥行 ", housing_depth, " mm"));
echo("上下2ポケット式: サーボ位置を0度と180度で交互に切り替える");

if (PART == "rotor") {
    // 軸をZ向きにし、広い円形面をベッドへ置く。
    translate([0, 0, rotor_thickness/2])
        rotate([90, 0, 0]) rotor_mechanical();
} else if (PART == "housing") {
    translate([0, 0, housing_depth/2])
        rotate([90, 0, 0]) housing_mechanical();
} else if (PART == "front_plate") {
    translate([0, 0, front_plate_thickness/2])
        rotate([90, 0, 0]) front_plate_mechanical();
} else if (PART == "rear_plate") {
    translate([0, 0, rear_plate_thickness/2])
        rotate([90, 0, 0]) rear_plate_mechanical();
} else if (PART == "hopper_adapter") {
    hopper_adapter();
} else if (PART == "outlet_adapter") {
    outlet_adapter();
} else {
    assembly_preview();
}
