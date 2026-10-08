/* ==========================================================================
 * びっくらポン 中空ドラム式180度カプセルディスペンサー
 * ==========================================================================
 *
 * 画像で検討した円筒ドラムをタイヤのように縦置きし、水平なモーター軸で
 * 0度と180度へ交互に回す機構。ドラム外周には180度対向の窓があり、
 * 上の窓でカプセルを1個受け、半回転後に下の窓から排出する。
 *
 * ドラム内部は単なる空洞ではなく、中央仕切りと左右ガイドによって
 * 1カプセル幅の上下2室に分かれている。これにより複数個の入り込みと
 * ドラム内部での横逃げを抑える。回転中はhousingの円形内壁が窓を塞ぐ。
 *
 * 印刷時の大きなブリッジを避けるため、回転体は次の2部品に分割する。
 *   rotor_body : 前面板、外周、内部仕切りを一体印刷
 *   rotor_lid  : 後ろ蓋、後面支持軸を一体印刷
 * M3ねじ4本で後ろ蓋をrotor_bodyへ固定する。
 *
 * 座標系（assembly表示時）:
 *   X = 左右、Y = 前後（回転軸）、Z = 上下
 * ========================================================================== */

// ---- 出力する部品 ----
PART = "assembly_cutaway";
// "rotor_body" / "rotor_lid" / "housing" /
// "front_plate" / "rear_plate" /
// "hopper_adapter" / "outlet_adapter" /
// "rotor" / "rotor_cutaway" / "assembly" / "assembly_cutaway"

// assembly表示時のローター位置。0と180が停止位置。
ROTOR_PREVIEW_ANGLE = 0;
SHOW_PREVIEW_CAPSULE = true;
SHOW_STEPPER_PREVIEW = true;

// ---- カプセル ----
// 必ず使用するカプセルを実測して変更すること。
capsule_diameter = 65;
pocket_clearance = 3.0;
throat_clearance = 3.5;

// ---- 中空ドラムローター ----
pocket_width = capsule_diameter + pocket_clearance;
pocket_depth = capsule_diameter + pocket_clearance;

drum_shell = 4;
drum_front_thickness = 4;
drum_lid_thickness = 4;
// 65mmカプセル時でも最大部品を160mm未満へ収めるため、上室の
// 高さをカプセル1個分＋最小限の逃げに詰める。
drum_inner_radius = capsule_diameter + 4;
drum_outer_radius = drum_inner_radius + drum_shell;
drum_depth = pocket_depth + drum_front_thickness + drum_lid_thickness;

divider_thickness = 4;
guide_wall_thickness = 4;

// 窓はカプセル径より少し広い扇形。角度を増やすほど入りやすいが、
// housingに塞がれる距離が短くなるため、必要以上に広げない。
window_angle = 2 * asin(pocket_width / (2 * drum_inner_radius)) + 10;

// 後ろ蓋固定用M3。ねじ頭はrear側から締める。
rotor_lid_screw_diameter = 3.4;
rotor_lid_screw_head_diameter = 6.4;
rotor_lid_screw_head_depth = 2.2;
rotor_body_pilot_diameter = 2.7;
rotor_screw_boss_diameter = 9;
rotor_screw_radius = drum_inner_radius - 11;
rotor_body_pilot_depth = 14;

// 後面支持軸
rear_pivot_diameter = 10;
rear_pivot_clearance = 0.6;
rear_pivot_length = 10;

// ---- 中央ステッピングモーター（初期値: NEMA17） ----
// 使用するモーターとシャフトハブを実測して調整すること。
stepper_body_size = 42.3;
stepper_body_depth = 40;
stepper_mount_spacing = 31;
stepper_mount_hole_diameter = 3.4;
stepper_pilot_diameter = 22.5;
stepper_shaft_diameter = 5;
stepper_shaft_clearance = 0.4;
stepper_shaft_length = 24;
stepper_shaft_engagement_depth = 14;

// ドラム前面へ市販の5mmシャフト用フランジハブを固定する4穴。
// ハブ製品によって穴ピッチが異なるため、必ず実物に合わせること。
rotor_hub_hole_circle = 18;
rotor_hub_mount_hole_diameter = 3.2;

// ---- ケース／前後プレート ----
radial_clearance = 0.8;
axial_clearance = 0.7;
housing_wall = 5;
housing_depth = drum_depth + axial_clearance * 2;
housing_width = (drum_outer_radius + housing_wall) * 2;
housing_height = housing_width;
throat_diameter = capsule_diameter + throat_clearance;

front_plate_thickness = 4;
rear_plate_thickness = 4;
case_bolt_diameter = 4.4;
case_bolt_edge = 9;

// ---- ホッパー／排出口アダプター ----
adapter_flange_width = 90;
adapter_flange_depth = housing_depth;
adapter_flange_thickness = 4;
adapter_wall = 3.5;
hopper_neck_height = 32;
outlet_neck_height = 20;
adapter_bolt_diameter = 3.4;
adapter_bolt_x = 34;
adapter_bolt_y = housing_depth/2 - 7;

$fn = 120;

// ==========================================================================
// 共通ヘルパー
// ==========================================================================

module cylinder_y(d, h) {
    rotate([90, 0, 0]) cylinder(d=d, h=h, center=true);
}

// XZ平面上の扇形をY方向へ押し出す。
module sector_y(radius, center_angle, sweep_angle, depth, steps=24) {
    start_angle = center_angle - sweep_angle/2;
    rotate([90, 0, 0])
        linear_extrude(height=depth, center=true)
            polygon(points=concat(
                [[0, 0]],
                [for (i = [0:steps])
                    [radius*cos(start_angle + sweep_angle*i/steps),
                     radius*sin(start_angle + sweep_angle*i/steps)]]
            ));
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

module rotor_lid_screw_pattern(depth, diameter, y_center) {
    for (angle = [45, 135, 225, 315])
        translate([
            rotor_screw_radius*cos(angle),
            y_center,
            rotor_screw_radius*sin(angle)
        ])
            cylinder_y(diameter, depth);
}

module stepper_mount_pattern(depth, diameter, y_center=0) {
    for (x = [-stepper_mount_spacing/2, stepper_mount_spacing/2])
        for (z = [-stepper_mount_spacing/2, stepper_mount_spacing/2])
            translate([x, y_center, z])
                cylinder_y(diameter, depth);
}

module rotor_hub_mount_pattern(depth, diameter, y_center) {
    for (angle = [45, 135, 225, 315])
        translate([
            rotor_hub_hole_circle/2*cos(angle),
            y_center,
            rotor_hub_hole_circle/2*sin(angle)
        ])
            cylinder_y(diameter, depth);
}

// ==========================================================================
// 中空ドラムローター本体
// ==========================================================================

module drum_side_shell(body_depth) {
    difference() {
        difference() {
            cylinder_y(drum_outer_radius*2, body_depth);
            cylinder_y(drum_inner_radius*2, body_depth + 2);
        }

        // 上下180度対向のカプセル窓。
        for (angle = [90, 270])
            sector_y(
                drum_outer_radius + 3,
                angle,
                window_angle,
                body_depth + 4
            );
    }
}

module internal_divider_and_guides() {
    // 前面板へ少し食い込ませ、面接触だけの非一体形状になるのを防ぐ。
    feature_depth = pocket_depth + 0.8;
    feature_center_y = -0.4;

    // 中央の床。半回転すると反対側ポケットの天井になる。
    intersection() {
        translate([0, feature_center_y, 0])
            cylinder_y(drum_inner_radius*2 + 0.4, feature_depth);
        translate([0, feature_center_y, 0])
            cube([
                pocket_width + guide_wall_thickness*2,
                feature_depth,
                divider_thickness
            ], center=true);
    }

    // カプセルが左右へ逃げないための2枚のガイド。
    for (x = [
        -(pocket_width + guide_wall_thickness)/2,
         (pocket_width + guide_wall_thickness)/2
        ])
        intersection() {
            translate([0, feature_center_y, 0])
                cylinder_y(drum_inner_radius*2 + 0.4, feature_depth);
            translate([x, feature_center_y, 0])
                cube([
                    guide_wall_thickness,
                    feature_depth,
                    drum_inner_radius*2 + 1
                ], center=true);
        }
}

module rotor_body_raw(include_front_face=true) {
    body_depth = drum_depth - drum_lid_thickness;
    body_center_y = -drum_lid_thickness/2;
    front_y = -drum_depth/2 + drum_front_thickness/2;

    union() {
        translate([0, body_center_y, 0])
            drum_side_shell(body_depth);

        if (include_front_face)
            translate([0, front_y, 0])
                cylinder_y(drum_outer_radius*2, drum_front_thickness);

        internal_divider_and_guides();

        // 後ろ蓋ねじ用ボス。カプセル通路の外側へ配置。
        rotor_lid_screw_pattern(
            pocket_depth + 0.8,
            rotor_screw_boss_diameter,
            -0.4
        );
    }
}

module rotor_body_mechanical(include_front_face=true) {
    body_rear_y = drum_depth/2 - drum_lid_thickness;
    front_surface_y = -drum_depth/2;
    front_face_y = front_surface_y + drum_front_thickness/2;

    difference() {
        rotor_body_raw(include_front_face);

        if (include_front_face) {
            // NEMA17の5mm軸がドラム中心へ入る穴。
            translate([
                0,
                front_surface_y + stepper_shaft_engagement_depth/2,
                0
            ])
                cylinder_y(
                    stepper_shaft_diameter + stepper_shaft_clearance,
                    stepper_shaft_engagement_depth + 1
                );

            // 市販のシャフト用フランジハブをドラム前面へ固定する穴。
            rotor_hub_mount_pattern(
                drum_front_thickness + 2,
                rotor_hub_mount_hole_diameter,
                front_face_y
            );
        }

        // 本体側はM3タッピング用の止まり穴。
        rotor_lid_screw_pattern(
            rotor_body_pilot_depth + 1,
            rotor_body_pilot_diameter,
            body_rear_y - rotor_body_pilot_depth/2 + 0.5
        );
    }
}

// ==========================================================================
// ドラム後ろ蓋
// ==========================================================================

module rotor_lid_mechanical() {
    lid_y = drum_depth/2 - drum_lid_thickness/2;
    pivot_y = drum_depth/2 + rear_pivot_length/2;

    difference() {
        union() {
            translate([0, lid_y, 0])
                cylinder_y(drum_outer_radius*2, drum_lid_thickness);

            translate([0, pivot_y, 0])
                cylinder_y(rear_pivot_diameter, rear_pivot_length);
        }

        rotor_lid_screw_pattern(
            drum_lid_thickness + 2,
            rotor_lid_screw_diameter,
            lid_y
        );

        // housingとのすき間へねじ頭が出ないよう、低頭M3用の座ぐりを設ける。
        rotor_lid_screw_pattern(
            rotor_lid_screw_head_depth + 0.4,
            rotor_lid_screw_head_diameter,
            drum_depth/2 - rotor_lid_screw_head_depth/2 + 0.1
        );
    }
}

module rotor_mechanical() {
    union() {
        rotor_body_mechanical(true);
        rotor_lid_mechanical();
    }
}

// ==========================================================================
// ローター外周ケース
// ==========================================================================

module housing_mechanical() {
    channel_start_z = drum_outer_radius - 10;
    channel_height = housing_height/2 - channel_start_z + 3;

    difference() {
        cube([housing_width, housing_depth, housing_height], center=true);

        // ローターが回る円形空間。
        cylinder_y(
            drum_outer_radius*2 + radial_clearance*2,
            housing_depth + 2
        );

        // 上下の単列カプセル通路。停止位置でのみドラム窓とつながる。
        translate([
            -throat_diameter/2,
            -(housing_depth + 2)/2,
            channel_start_z
        ])
            cube([
                throat_diameter,
                housing_depth + 2,
                channel_height
            ]);

        translate([
            -throat_diameter/2,
            -(housing_depth + 2)/2,
            -housing_height/2 - 3
        ])
            cube([
                throat_diameter,
                housing_depth + 2,
                channel_height
            ]);

        case_bolt_pattern(housing_depth + 4);

        // 上面・下面アダプター固定用M3穴。
        for (x = [-adapter_bolt_x, adapter_bolt_x])
            for (y = [-adapter_bolt_y, adapter_bolt_y]) {
                translate([x, y, drum_outer_radius - 2])
                    cylinder(
                        d=adapter_bolt_diameter,
                        h=housing_height/2 - drum_outer_radius + 4
                    );
                translate([x, y, -housing_height/2 - 2])
                    cylinder(
                        d=adapter_bolt_diameter,
                        h=housing_height/2 - drum_outer_radius + 4
                    );
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

        // NEMA17の中央ボスとシャフトを通す穴。
        cylinder_y(stepper_pilot_diameter, front_plate_thickness + 2);

        // NEMA17標準31mm角のM3固定穴。
        stepper_mount_pattern(
            front_plate_thickness + 2,
            stepper_mount_hole_diameter
        );
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

module preview_capsule() {
    capsule_center_z = divider_thickness/2 + capsule_diameter/2;
    color([0.86, 0.04, 0.07, 0.95])
        translate([0, 0, capsule_center_z])
            sphere(d=capsule_diameter);
}

module preview_stepper() {
    front_plate_outer_y = -(housing_depth/2 + front_plate_thickness);
    body_center_y = front_plate_outer_y - stepper_body_depth/2;
    boss_center_y = front_plate_outer_y + 1;
    shaft_center_y = front_plate_outer_y + stepper_shaft_length/2;

    color([0.16, 0.18, 0.20, 0.9])
        translate([0, body_center_y, 0])
            cube([
                stepper_body_size,
                stepper_body_depth,
                stepper_body_size
            ], center=true);

    color([0.35, 0.37, 0.39, 0.95])
        translate([0, boss_center_y, 0])
            cylinder_y(stepper_pilot_diameter - 0.5, 2);

    color([0.72, 0.74, 0.76, 1.0])
        translate([0, shaft_center_y, 0])
            cylinder_y(stepper_shaft_diameter, stepper_shaft_length);
}

module rotor_cutaway_preview() {
    color([1.0, 0.38, 0.02, 1.0])
        rotor_body_mechanical(false);

    color([0.30, 0.58, 0.88, 0.28])
        rotor_lid_mechanical();

    preview_capsule();
}

module assembly_preview(cutaway=false) {
    front_y = -(housing_depth/2 + front_plate_thickness/2);
    rear_y = housing_depth/2 + rear_plate_thickness/2;

    color("DimGray", cutaway ? 0.22 : 1.0)
        housing_mechanical();

    rotate([0, ROTOR_PREVIEW_ANGLE, 0]) {
        color("DarkOrange", cutaway ? 0.82 : 1.0)
            rotor_body_mechanical(!cutaway);

        color("Orange", cutaway ? 0.35 : 1.0)
            rotor_lid_mechanical();

        if (SHOW_PREVIEW_CAPSULE)
            preview_capsule();
    }

    if (!cutaway)
        translate([0, front_y, 0])
            color("LightSteelBlue", 0.55)
                front_plate_mechanical();

    if (SHOW_STEPPER_PREVIEW && !cutaway)
        preview_stepper();

    translate([0, rear_y, 0])
        color("LightSteelBlue", cutaway ? 0.25 : 0.55)
            rear_plate_mechanical();

    translate([
        -adapter_flange_width/2,
        -adapter_flange_depth/2,
        housing_height/2
    ])
        color("PaleGreen", cutaway ? 0.5 : 0.8)
            hopper_adapter();

    translate([
        adapter_flange_width/2,
        -adapter_flange_depth/2,
        -housing_height/2
    ])
        rotate([0, 180, 0])
            color("Khaki", cutaway ? 0.5 : 0.8)
                outlet_adapter();
}

// ==========================================================================
// 寸法表示と印刷向け配置
// ==========================================================================

echo(str("カプセル直径: ", capsule_diameter, " mm"));
echo(str("ドラム外径: ", drum_outer_radius*2,
         " x 奥行 ", drum_depth, " mm"));
echo(str("ドラム窓角度: ", window_angle, " degrees"));
echo(str("ケース: ", housing_width, " x ", housing_height,
         " x 奥行 ", housing_depth, " mm"));
echo("中空ドラム式: 0度と180度を交互に使用");

if (PART == "rotor_body") {
    // 前面をベッドへ置き、内部壁と外周を上へ積層する。
    translate([0, 0, drum_depth/2])
        rotate([90, 0, 0])
            rotor_body_mechanical(true);
} else if (PART == "rotor_lid") {
    // 蓋の内面をベッドへ置き、支持軸を上向きにする。
    translate([0, 0, -(drum_depth/2 - drum_lid_thickness)])
        rotate([90, 0, 0])
            rotor_lid_mechanical();
} else if (PART == "rotor") {
    color([0.68, 0.70, 0.68, 1.0])
        rotor_mechanical();
} else if (PART == "rotor_cutaway") {
    rotor_cutaway_preview();
} else if (PART == "housing") {
    translate([0, 0, housing_depth/2])
        rotate([90, 0, 0])
            housing_mechanical();
} else if (PART == "front_plate") {
    translate([0, 0, front_plate_thickness/2])
        rotate([90, 0, 0])
            front_plate_mechanical();
} else if (PART == "rear_plate") {
    translate([0, 0, rear_plate_thickness/2])
        rotate([90, 0, 0])
            rear_plate_mechanical();
} else if (PART == "hopper_adapter") {
    hopper_adapter();
} else if (PART == "outlet_adapter") {
    outlet_adapter();
} else if (PART == "assembly") {
    assembly_preview(false);
} else {
    assembly_preview(true);
}
