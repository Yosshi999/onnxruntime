# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import argparse
import os
import re
import sys
from pathlib import Path


# What does the names of our C API tarball/zip files looks like
# os: win, linux, osx
# ep: cuda, tensorrt, None
def get_package_name(os, cpu_arch, ep):
    pkg_name = None
    if os == "win":
        pkg_name = "onnxruntime-win-"
        pkg_name += cpu_arch
        if ep == "cuda":
            pkg_name += "-cuda"
        elif ep == "tensorrt":
            pkg_name += "-tensorrt"
    elif os == "linux":
        pkg_name = "onnxruntime-linux-"
        pkg_name += cpu_arch
        if ep == "cuda":
            pkg_name += "-cuda"
        elif ep == "tensorrt":
            pkg_name += "-tensorrt"
    elif os == "osx":
        pkg_name = "onnxruntime-osx-" + cpu_arch
    return pkg_name


# Currently we take onnxruntime_providers_cuda from CUDA build
# And onnxruntime, onnxruntime_providers_shared and
# onnxruntime_providers_tensorrt from tensorrt build
def is_this_file_needed(ep, filename):
    return (ep != "cuda" or "cuda" in filename) and (ep != "tensorrt" or "cuda" not in filename)


# nuget_artifacts_dir: the directory with uncompressed C API tarball/zip files
# ep: cuda, tensorrt, None
# files_list: a list of xml string pieces to append
# This function has no return value. It updates files_list directly
def generate_file_list_for_ep(nuget_artifacts_dir, ep, files_list, include_pdbs):
    for child in nuget_artifacts_dir.iterdir():
        if not child.is_dir():
            continue

        for cpu_arch in ["x86", "x64", "arm", "arm64"]:
            if child.name == get_package_name("win", cpu_arch, ep):
                child = child / "lib"
                for child_file in child.iterdir():
                    suffixes = [".dll", ".lib", ".pdb"] if include_pdbs else [".dll", ".lib"]
                    if child_file.suffix in suffixes and is_this_file_needed(ep, child_file.name):
                        files_list.append(
                            '<file src="' + str(child_file) + '" target="runtimes/win-%s/native"/>' % cpu_arch
                        )
        for cpu_arch in ["x86_64", "arm64"]:
            if child.name == get_package_name("osx", cpu_arch, ep):
                child = child / "lib"
                if cpu_arch == "x86_64":
                    cpu_arch = "x64"
                for child_file in child.iterdir():
                    # Check if the file has digits like onnxruntime.1.8.0.dylib. We can skip such things
                    is_versioned_dylib = re.match(r".*[\.\d+]+\.dylib$", child_file.name)
                    if child_file.is_file() and child_file.suffix == ".dylib" and not is_versioned_dylib:
                        files_list.append(
                            '<file src="' + str(child_file) + '" target="runtimes/osx.10.14-%s/native"/>' % cpu_arch
                        )
        for cpu_arch in ["x64", "aarch64"]:
            if child.name == get_package_name("linux", cpu_arch, ep):
                child = child / "lib"
                if cpu_arch == "x86_64":
                    cpu_arch = "x64"
                elif cpu_arch == "aarch64":
                    cpu_arch = "arm64"
                for child_file in child.iterdir():
                    if not child_file.is_file():
                        continue
                    if child_file.suffix == ".so" and is_this_file_needed(ep, child_file.name):
                        files_list.append(
                            '<file src="' + str(child_file) + '" target="runtimes/linux-%s/native"/>' % cpu_arch
                        )

        if child.name == "onnxruntime-android":
            for child_file in child.iterdir():
                if child_file.suffix in [".aar"]:
                    files_list.append('<file src="' + str(child_file) + '" target="runtimes/android/native"/>')

        if child.name == "onnxruntime-ios-xcframework":
            files_list.append('<file src="' + str(child) + "\\**" '" target="runtimes/ios/native"/>')


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="ONNX Runtime create nuget spec script " "(for hosting native shared library artifacts)", usage=""
    )
    # Main arguments
    parser.add_argument("--package_name", required=True, help="ORT package name. Eg: Microsoft.ML.OnnxRuntime.Gpu")
    parser.add_argument("--package_version", required=True, help="ORT package version. Eg: 1.0.0")
    parser.add_argument("--target_architecture", required=True, help="Eg: x64")
    parser.add_argument("--build_config", required=True, help="Eg: RelWithDebInfo")
    parser.add_argument("--ort_build_path", required=True, help="ORT build directory.")
    parser.add_argument("--native_build_path", required=True, help="Native build output directory.")
    parser.add_argument("--packages_path", required=True, help="Nuget packages output directory.")
    parser.add_argument("--sources_path", required=True, help="OnnxRuntime source code root.")
    parser.add_argument("--commit_id", required=True, help="The last commit id included in this package.")
    parser.add_argument(
        "--is_release_build",
        required=False,
        default=None,
        type=str,
        help="Flag indicating if the build is a release build. Accepted values: true/false.",
    )
    parser.add_argument(
        "--execution_provider",
        required=False,
        default="None",
        type=str,
        choices=["cuda", "dnnl", "openvino", "tensorrt", "snpe", "None"],
        help="The selected execution provider for this build.",
    )
    parser.add_argument("--dependency_id", required=False, default="None", type=str, help="ependency id.")
    parser.add_argument("--dependency_version", required=False, default="None", type=str, help="dependency version.")

    return parser.parse_args()


def generate_id(list, package_name):
    list.append("<id>" + package_name + "</id>")


def generate_version(list, package_version):
    list.append("<version>" + package_version + "</version>")


def generate_authors(list, authors):
    list.append("<authors>" + authors + "</authors>")


def generate_owners(list, owners):
    list.append("<owners>" + owners + "</owners>")


def generate_description(list, package_name):
    description = ""

    if package_name == "Microsoft.AI.MachineLearning":
        description = "This package contains Windows ML binaries."
    elif "Microsoft.ML.OnnxRuntime" in package_name:  # This is a Microsoft.ML.OnnxRuntime.* package
        description = (
            "This package contains native shared library artifacts " "for all supported platforms of ONNX Runtime."
        )

    list.append("<description>" + description + "</description>")


def generate_copyright(list, copyright):
    list.append("<copyright>" + copyright + "</copyright>")


def generate_tags(list, tags):
    list.append("<tags>" + tags + "</tags>")


def generate_icon(list, icon_file):
    list.append("<icon>" + icon_file + "</icon>")


def generate_license(list):
    list.append('<license type="file">LICENSE.txt</license>')


def generate_project_url(list, project_url):
    list.append("<projectUrl>" + project_url + "</projectUrl>")


def generate_repo_url(list, repo_url, commit_id):
    list.append('<repository type="git" url="' + repo_url + '"' + ' commit="' + commit_id + '" />')


def generate_dependencies(xml_text, package_name, version, dependency_id, dependency_version):
    if package_name in ("Microsoft.ML.OnnxRuntime.Snpe", "Microsoft.ML.OnnxRuntime.Snpe_Win"):
        xml_text.append("<dependencies>")
        xml_text.append('<dependency id="' + dependency_id + '" version="' + dependency_version + '"/>')
        xml_text.append("</dependencies>")
        return

    dml_dependency = (
        '<dependency id="Microsoft.AI.DirectML.Preview" version="1.9.0-devd10042c94985065a565c042540e15eb75b554663"/>'
    )

    if package_name == "Microsoft.AI.MachineLearning":
        xml_text.append("<dependencies>")

        # Support .Net Core
        xml_text.append('<group targetFramework="net5.0">')
        xml_text.append(dml_dependency)
        xml_text.append("</group>")
        # UAP10.0.16299, This is the earliest release of the OS that supports .NET Standard apps
        xml_text.append('<group targetFramework="UAP10.0.16299">')
        xml_text.append(dml_dependency)
        xml_text.append("</group>")
        # Support Native C++
        xml_text.append('<group targetFramework="native">')
        xml_text.append(dml_dependency)
        xml_text.append("</group>")

        xml_text.append("</dependencies>")
    else:
        include_dml = package_name == "Microsoft.ML.OnnxRuntime.DirectML.Preview"

        xml_text.append("<dependencies>")
        # Support .Net Core
        xml_text.append('<group targetFramework="NETCOREAPP">')
        xml_text.append('<dependency id="Microsoft.ML.OnnxRuntime.Managed"' + ' version="' + version + '"/>')
        if include_dml:
            xml_text.append(dml_dependency)
        xml_text.append("</group>")
        # Support .Net Standard
        xml_text.append('<group targetFramework="NETSTANDARD">')
        xml_text.append('<dependency id="Microsoft.ML.OnnxRuntime.Managed"' + ' version="' + version + '"/>')
        if include_dml:
            xml_text.append(dml_dependency)
        xml_text.append("</group>")
        # Support .Net Framework
        xml_text.append('<group targetFramework="NETFRAMEWORK">')
        xml_text.append('<dependency id="Microsoft.ML.OnnxRuntime.Managed"' + ' version="' + version + '"/>')
        if include_dml:
            xml_text.append(dml_dependency)
        xml_text.append("</group>")
        if package_name == "Microsoft.ML.OnnxRuntime":
            # Support monoandroid11.0
            xml_text.append('<group targetFramework="monoandroid11.0">')
            xml_text.append('<dependency id="Microsoft.ML.OnnxRuntime.Managed"' + ' version="' + version + '"/>')
            xml_text.append("</group>")
            # Support xamarinios10
            xml_text.append('<group targetFramework="xamarinios10">')
            xml_text.append('<dependency id="Microsoft.ML.OnnxRuntime.Managed"' + ' version="' + version + '"/>')
            xml_text.append("</group>")
        # Support Native C++
        if include_dml:
            xml_text.append('<group targetFramework="native">')
            xml_text.append(dml_dependency)
            xml_text.append("</group>")

        xml_text.append("</dependencies>")


def get_env_var(key):
    return os.environ.get(key)


def generate_release_notes(list):
    list.append("<releaseNotes>")
    list.append("Release Def:")

    branch = get_env_var("BUILD_SOURCEBRANCH")
    list.append("\t" + "Branch: " + (branch if branch is not None else ""))

    version = get_env_var("BUILD_SOURCEVERSION")
    list.append("\t" + "Commit: " + (version if version is not None else ""))

    build_id = get_env_var("BUILD_BUILDID")
    list.append(
        "\t"
        + "Build: https://aiinfra.visualstudio.com/Lotus/_build/results?buildId="
        + (build_id if build_id is not None else "")
    )

    list.append("</releaseNotes>")


def generate_metadata(list, args):
    metadata_list = ["<metadata>"]
    generate_id(metadata_list, args.package_name)
    generate_version(metadata_list, args.package_version)
    generate_authors(metadata_list, "Microsoft")
    generate_owners(metadata_list, "Microsoft")
    generate_description(metadata_list, args.package_name)
    generate_copyright(metadata_list, "\xc2\xa9 " + "Microsoft Corporation. All rights reserved.")
    generate_tags(metadata_list, "ONNX ONNX Runtime Machine Learning")
    generate_icon(metadata_list, "ORT_icon_for_light_bg.png")
    generate_license(metadata_list)
    generate_project_url(metadata_list, "https://github.com/Microsoft/onnxruntime")
    generate_repo_url(metadata_list, "https://github.com/Microsoft/onnxruntime.git", args.commit_id)
    generate_dependencies(
        metadata_list, args.package_name, args.package_version, args.dependency_id, args.dependency_version
    )
    generate_release_notes(metadata_list)
    metadata_list.append("</metadata>")

    list += metadata_list


def generate_files(list, args):
    files_list = ["<files>"]

    is_cpu_package = args.package_name in ["Microsoft.ML.OnnxRuntime", "Microsoft.ML.OnnxRuntime.OpenMP"]
    is_mklml_package = args.package_name == "Microsoft.ML.OnnxRuntime.MKLML"
    is_cuda_gpu_package = args.package_name == "Microsoft.ML.OnnxRuntime.Gpu"
    is_dml_package = args.package_name == "Microsoft.ML.OnnxRuntime.DirectML"
    is_windowsai_package = args.package_name == "Microsoft.AI.MachineLearning"
    is_snpe_package_win = args.package_name == "Microsoft.ML.OnnxRuntime.Snpe_Win"

    includes_winml = is_windowsai_package
    includes_directml = (is_dml_package or is_windowsai_package) and (
        args.target_architecture == "x64" or args.target_architecture == "x86"
    )

    is_windows_build = is_windows()

    nuget_dependencies = {}

    if is_windows_build:
        nuget_dependencies = {
            "mklml": "mklml.dll",
            "openmp": "libiomp5md.dll",
            "dnnl": "dnnl.dll",
            "tvm": "tvm.dll",
            "providers_shared_lib": "onnxruntime_providers_shared.dll",
            "dnnl_ep_shared_lib": "onnxruntime_providers_dnnl.dll",
            "tensorrt_ep_shared_lib": "onnxruntime_providers_tensorrt.dll",
            "openvino_ep_shared_lib": "onnxruntime_providers_openvino.dll",
            "cuda_ep_shared_lib": "onnxruntime_providers_cuda.dll",
            "onnxruntime_perf_test": "onnxruntime_perf_test.exe",
            "onnx_test_runner": "onnx_test_runner.exe",
        }

        copy_command = "copy"
        runtimes_target = '" target="runtimes\\win-'
    else:
        nuget_dependencies = {
            "mklml": "libmklml_intel.so",
            "mklml_1": "libmklml_gnu.so",
            "openmp": "libiomp5.so",
            "dnnl": "libdnnl.so.1",
            "tvm": "libtvm.so.0.5.1",
            "providers_shared_lib": "libonnxruntime_providers_shared.so",
            "dnnl_ep_shared_lib": "libonnxruntime_providers_dnnl.so",
            "tensorrt_ep_shared_lib": "libonnxruntime_providers_tensorrt.so",
            "openvino_ep_shared_lib": "libonnxruntime_providers_openvino.so",
            "cuda_ep_shared_lib": "libonnxruntime_providers_cuda.so",
            "onnxruntime_perf_test": "onnxruntime_perf_test",
            "onnx_test_runner": "onnx_test_runner",
        }

        copy_command = "cp"
        runtimes_target = '" target="runtimes\\linux-'

    if is_windowsai_package:
        runtimes_native_folder = "_native"
    else:
        runtimes_native_folder = "native"

    runtimes = '{}{}\\{}"'.format(runtimes_target, args.target_architecture, runtimes_native_folder)

    # Process headers
    files_list.append(
        "<file src="
        + '"'
        + os.path.join(args.sources_path, "include\\onnxruntime\\core\\session\\onnxruntime_*.h")
        + '" target="build\\native\\include" />'
    )
    files_list.append(
        "<file src="
        + '"'
        + os.path.join(args.sources_path, "include\\onnxruntime\\core\\framework\\provider_options.h")
        + '" target="build\\native\\include" />'
    )
    files_list.append(
        "<file src="
        + '"'
        + os.path.join(args.sources_path, "include\\onnxruntime\\core\\providers\\cpu\\cpu_provider_factory.h")
        + '" target="build\\native\\include" />'
    )

    if args.execution_provider == "openvino":
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(
                args.sources_path, "include\\onnxruntime\\core\\providers\\openvino\\openvino_provider_factory.h"
            )
            + '" target="build\\native\\include" />'
        )

    if args.execution_provider == "tensorrt":
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(
                args.sources_path, "include\\onnxruntime\\core\\providers\\tensorrt\\tensorrt_provider_factory.h"
            )
            + '" target="build\\native\\include" />'
        )

    if args.execution_provider == "dnnl":
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.sources_path, "include\\onnxruntime\\core\\providers\\dnnl\\dnnl_provider_factory.h")
            + '" target="build\\native\\include" />'
        )

    if includes_directml:
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.sources_path, "include\\onnxruntime\\core\\providers\\dml\\dml_provider_factory.h")
            + '" target="build\\native\\include" />'
        )

    if includes_winml:
        # Add microsoft.ai.machinelearning headers
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.ort_build_path, args.build_config, "microsoft.ai.machinelearning.h")
            + '" target="build\\native\\include\\abi\\Microsoft.AI.MachineLearning.h" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.sources_path, "winml\\api\\dualapipartitionattribute.h")
            + '" target="build\\native\\include\\abi\\dualapipartitionattribute.h" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.ort_build_path, args.build_config, "microsoft.ai.machinelearning.native.h")
            + '" target="build\\native\\include\\Microsoft.AI.MachineLearning.Native.h" />'
        )
        # Add custom operator headers
        mlop_path = "onnxruntime\\core\\providers\\dml\\dmlexecutionprovider\\inc\\mloperatorauthor.h"
        files_list.append(
            "<file src=" + '"' + os.path.join(args.sources_path, mlop_path) + '" target="build\\native\\include" />'
        )
        # Process microsoft.ai.machinelearning.winmd
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.ort_build_path, args.build_config, "microsoft.ai.machinelearning.winmd")
            + '" target="winmds\\Microsoft.AI.MachineLearning.winmd" />'
        )
        # Process microsoft.ai.machinelearning.experimental.winmd
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.ort_build_path, args.build_config, "microsoft.ai.machinelearning.experimental.winmd")
            + '" target="winmds\\Microsoft.AI.MachineLearning.Experimental.winmd" />'
        )
        if args.target_architecture == "x64":
            interop_dll_path = "Microsoft.AI.MachineLearning.Interop\\net5.0-windows10.0.17763.0"
            interop_dll = interop_dll_path + "\\Microsoft.AI.MachineLearning.Interop.dll"
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, interop_dll)
                + '" target="lib\\net5.0\\Microsoft.AI.MachineLearning.Interop.dll" />'
            )
            interop_pdb_path = "Microsoft.AI.MachineLearning.Interop\\net5.0-windows10.0.17763.0"
            interop_pdb = interop_pdb_path + "\\Microsoft.AI.MachineLearning.Interop.pdb"
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, interop_pdb)
                + '" target="lib\\net5.0\\Microsoft.AI.MachineLearning.Interop.pdb" />'
            )

    if args.package_name == "Microsoft.ML.OnnxRuntime.Snpe_Win":
        files_list.append(
            "<file src=" + '"' + os.path.join(args.native_build_path, "onnx_test_runner.exe") + runtimes + " />"
        )
        files_list.append(
            "<file src=" + '"' + os.path.join(args.native_build_path, "onnxruntime_perf_test.exe") + runtimes + " />"
        )

    is_ado_packaging_build = False
    # Process runtimes
    # Process onnxruntime import lib, dll, and pdb
    # for Snpe android build
    if is_windows_build:
        nuget_artifacts_dir = Path(args.native_build_path) / "nuget-artifacts"
        # the winml package includes pdbs. for other packages exclude them.
        include_pdbs = includes_winml
        if nuget_artifacts_dir.exists():
            # Code path for ADO build pipeline, the files under 'nuget-artifacts' are
            # downloaded from other build jobs
            if is_cuda_gpu_package:
                ep_list = ["tensorrt", "cuda", None]
            else:
                ep_list = [None]
            for ep in ep_list:
                generate_file_list_for_ep(nuget_artifacts_dir, ep, files_list, include_pdbs)
            is_ado_packaging_build = True
        else:
            # Code path for local dev build
            files_list.append(
                "<file src=" + '"' + os.path.join(args.native_build_path, "onnxruntime.lib") + runtimes + " />"
            )
            files_list.append(
                "<file src=" + '"' + os.path.join(args.native_build_path, "onnxruntime.dll") + runtimes + " />"
            )
            if include_pdbs and os.path.exists(os.path.join(args.native_build_path, "onnxruntime.pdb")):
                files_list.append(
                    "<file src=" + '"' + os.path.join(args.native_build_path, "onnxruntime.pdb") + runtimes + " />"
                )
    elif args.package_name == "Microsoft.ML.OnnxRuntime.Snpe":
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, "libonnxruntime.so")
            + '" target="runtimes\\android-arm64\\native" />'
        )
    else:
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, "nuget-staging/usr/local/lib", "libonnxruntime.so")
            + '" target="runtimes\\linux-'
            + args.target_architecture
            + '\\native" />'
        )

    if includes_winml:
        # Process microsoft.ai.machinelearning import lib, dll, and pdb
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, "microsoft.ai.machinelearning.lib")
            + runtimes_target
            + args.target_architecture
            + "\\_native"
            + '\\Microsoft.AI.MachineLearning.lib" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, "microsoft.ai.machinelearning.dll")
            + runtimes_target
            + args.target_architecture
            + "\\_native"
            + '\\Microsoft.AI.MachineLearning.dll" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, "microsoft.ai.machinelearning.pdb")
            + runtimes_target
            + args.target_architecture
            + "\\_native"
            + '\\Microsoft.AI.MachineLearning.pdb" />'
        )
    # Process execution providers which are built as shared libs
    if args.execution_provider == "tensorrt" and not is_ado_packaging_build:
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["providers_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["cuda_ep_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["tensorrt_ep_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )

    if args.execution_provider == "dnnl":
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["providers_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["dnnl_ep_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )

    if args.execution_provider == "openvino":
        openvino_path = get_env_var("INTEL_OPENVINO_DIR")
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["providers_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["openvino_ep_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )

        if is_windows():
            if "2022" in openvino_path:
                dll_list_path = os.path.join(openvino_path, "runtime\\bin\\intel64\\Release\\")
                tbb_list_path = os.path.join(openvino_path, "runtime\\3rdparty\\tbb\\bin\\")
            else:
                dll_list_path = os.path.join(
                    openvino_path, "deployment_tools\\inference_engine\\bin\\intel64\\Release\\"
                )
                tbb_list_path = os.path.join(openvino_path, "deployment_tools\\inference_engine\\external\\tbb\\bin\\")
                ngraph_list_path = os.path.join(openvino_path, "deployment_tools\\ngraph\\lib\\")
                for ngraph_element in os.listdir(ngraph_list_path):
                    if ngraph_element.endswith("dll"):
                        files_list.append(
                            "<file src="
                            + '"'
                            + os.path.join(ngraph_list_path, ngraph_element)
                            + runtimes_target
                            + args.target_architecture
                            + '\\native" />'
                        )
            for dll_element in os.listdir(dll_list_path):
                if dll_element.endswith("dll"):
                    files_list.append(
                        "<file src="
                        + '"'
                        + os.path.join(dll_list_path, dll_element)
                        + runtimes_target
                        + args.target_architecture
                        + '\\native" />'
                    )
            # plugins.xml
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(dll_list_path, "plugins.xml")
                + runtimes_target
                + args.target_architecture
                + '\\native" />'
            )
            # usb-ma2x8x.mvcmd
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(dll_list_path, "usb-ma2x8x.mvcmd")
                + runtimes_target
                + args.target_architecture
                + '\\native" />'
            )
            for tbb_element in os.listdir(tbb_list_path):
                if tbb_element.endswith("dll"):
                    files_list.append(
                        "<file src="
                        + '"'
                        + os.path.join(tbb_list_path, tbb_element)
                        + runtimes_target
                        + args.target_architecture
                        + '\\native" />'
                    )

    if args.execution_provider == "cuda" or is_cuda_gpu_package and not is_ado_packaging_build:
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["providers_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )
        files_list.append(
            "<file src="
            + '"'
            + os.path.join(args.native_build_path, nuget_dependencies["cuda_ep_shared_lib"])
            + runtimes_target
            + args.target_architecture
            + '\\native" />'
        )

    # process all other library dependencies
    if is_cpu_package or is_cuda_gpu_package or is_dml_package or is_mklml_package:
        # Process dnnl dependency
        if os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["dnnl"])):
            files_list.append(
                "<file src=" + '"' + os.path.join(args.native_build_path, nuget_dependencies["dnnl"]) + runtimes + " />"
            )

        # Process mklml dependency
        if os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["mklml"])):
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, nuget_dependencies["mklml"])
                + runtimes
                + " />"
            )

        if is_linux() and os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["mklml_1"])):
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, nuget_dependencies["mklml_1"])
                + runtimes
                + " />"
            )

        # Process libiomp5md dependency
        if os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["openmp"])):
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, nuget_dependencies["openmp"])
                + runtimes
                + " />"
            )

        # Process tvm dependency
        if os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["tvm"])):
            files_list.append(
                "<file src=" + '"' + os.path.join(args.native_build_path, nuget_dependencies["tvm"]) + runtimes + " />"
            )

        # Some tools to be packaged in nightly build only, should not be released
        # These are copied to the runtimes folder for convenience of loading with the dlls
        if (
            args.is_release_build.lower() != "true"
            and args.target_architecture == "x64"
            and os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["onnxruntime_perf_test"]))
        ):
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, nuget_dependencies["onnxruntime_perf_test"])
                + runtimes
                + " />"
            )

        if (
            args.is_release_build.lower() != "true"
            and args.target_architecture == "x64"
            and os.path.exists(os.path.join(args.native_build_path, nuget_dependencies["onnx_test_runner"]))
        ):
            files_list.append(
                "<file src="
                + '"'
                + os.path.join(args.native_build_path, nuget_dependencies["onnx_test_runner"])
                + runtimes
                + " />"
            )

    # Process props and targets files
    if is_windowsai_package:
        windowsai_src = "Microsoft.AI.MachineLearning"
        windowsai_props = "Microsoft.AI.MachineLearning.props"
        windowsai_targets = "Microsoft.AI.MachineLearning.targets"
        windowsai_native_props = os.path.join(args.sources_path, "csharp", "src", windowsai_src, windowsai_props)
        windowsai_rules = "Microsoft.AI.MachineLearning.Rules.Project.xml"
        windowsai_native_rules = os.path.join(args.sources_path, "csharp", "src", windowsai_src, windowsai_rules)
        windowsai_native_targets = os.path.join(args.sources_path, "csharp", "src", windowsai_src, windowsai_targets)
        build = "build\\native"
        files_list.append("<file src=" + '"' + windowsai_native_props + '" target="' + build + '" />')
        # Process native targets
        files_list.append("<file src=" + '"' + windowsai_native_targets + '" target="' + build + '" />')
        # Process rules
        files_list.append("<file src=" + '"' + windowsai_native_rules + '" target="' + build + '" />')
        # Process .net5.0 targets
        if args.target_architecture == "x64":
            interop_src = "Microsoft.AI.MachineLearning.Interop"
            interop_props = "Microsoft.AI.MachineLearning.props"
            interop_targets = "Microsoft.AI.MachineLearning.targets"
            windowsai_net50_props = os.path.join(args.sources_path, "csharp", "src", interop_src, interop_props)
            windowsai_net50_targets = os.path.join(args.sources_path, "csharp", "src", interop_src, interop_targets)
            files_list.append("<file src=" + '"' + windowsai_net50_props + '" target="build\\net5.0" />')
            files_list.append("<file src=" + '"' + windowsai_net50_targets + '" target="build\\net5.0" />')

    if is_cpu_package or is_cuda_gpu_package or is_dml_package or is_mklml_package or is_snpe_package_win:
        # Process props file
        source_props = os.path.join(
            args.sources_path, "csharp", "src", "Microsoft.ML.OnnxRuntime", "targets", "netstandard", "props.xml"
        )
        target_props = os.path.join(
            args.sources_path,
            "csharp",
            "src",
            "Microsoft.ML.OnnxRuntime",
            "targets",
            "netstandard",
            args.package_name + ".props",
        )
        os.system(copy_command + " " + source_props + " " + target_props)
        files_list.append("<file src=" + '"' + target_props + '" target="build\\native" />')
        if not is_snpe_package_win:
            files_list.append("<file src=" + '"' + target_props + '" target="build\\netstandard1.1" />')
            files_list.append("<file src=" + '"' + target_props + '" target="build\\netstandard2.0" />')

        # Process targets file
        if is_snpe_package_win:
            source_targets = os.path.join(
                args.sources_path,
                "csharp",
                "src",
                "Microsoft.ML.OnnxRuntime",
                "targets",
                "netstandard",
                "targets_snpe.xml",
            )
        else:
            source_targets = os.path.join(
                args.sources_path, "csharp", "src", "Microsoft.ML.OnnxRuntime", "targets", "netstandard", "targets.xml"
            )
        target_targets = os.path.join(
            args.sources_path,
            "csharp",
            "src",
            "Microsoft.ML.OnnxRuntime",
            "targets",
            "netstandard",
            args.package_name + ".targets",
        )
        os.system(copy_command + " " + source_targets + " " + target_targets)
        files_list.append("<file src=" + '"' + target_targets + '" target="build\\native" />')
        if not is_snpe_package_win:
            files_list.append("<file src=" + '"' + target_targets + '" target="build\\netstandard1.1" />')
            files_list.append("<file src=" + '"' + target_targets + '" target="build\\netstandard2.0" />')

        # Process xamarin targets files
        if args.package_name == "Microsoft.ML.OnnxRuntime":
            monoandroid_source_targets = os.path.join(
                args.sources_path,
                "csharp",
                "src",
                "Microsoft.ML.OnnxRuntime",
                "targets",
                "monoandroid11.0",
                "targets.xml",
            )
            monoandroid_target_targets = os.path.join(
                args.sources_path,
                "csharp",
                "src",
                "Microsoft.ML.OnnxRuntime",
                "targets",
                "monoandroid11.0",
                args.package_name + ".targets",
            )
            os.system(copy_command + " " + monoandroid_source_targets + " " + monoandroid_target_targets)

            xamarinios_source_targets = os.path.join(
                args.sources_path, "csharp", "src", "Microsoft.ML.OnnxRuntime", "targets", "xamarinios10", "targets.xml"
            )
            xamarinios_target_targets = os.path.join(
                args.sources_path,
                "csharp",
                "src",
                "Microsoft.ML.OnnxRuntime",
                "targets",
                "xamarinios10",
                args.package_name + ".targets",
            )
            os.system(copy_command + " " + xamarinios_source_targets + " " + xamarinios_target_targets)

            files_list.append("<file src=" + '"' + monoandroid_target_targets + '" target="build\\monoandroid11.0" />')
            files_list.append(
                "<file src=" + '"' + monoandroid_target_targets + '" target="buildTransitive\\monoandroid11.0" />'
            )
            files_list.append("<file src=" + '"' + xamarinios_target_targets + '" target="build\\xamarinios10" />')
            files_list.append(
                "<file src=" + '"' + xamarinios_target_targets + '" target="buildTransitive\\xamarinios10" />'
            )

    # Process License, ThirdPartyNotices, Privacy
    files_list.append("<file src=" + '"' + os.path.join(args.sources_path, "LICENSE.txt") + '" target="LICENSE.txt" />')
    files_list.append(
        "<file src="
        + '"'
        + os.path.join(args.sources_path, "ThirdPartyNotices.txt")
        + '" target="ThirdPartyNotices.txt" />'
    )
    files_list.append(
        "<file src=" + '"' + os.path.join(args.sources_path, "docs", "Privacy.md") + '" target="Privacy.md" />'
    )
    files_list.append(
        "<file src="
        + '"'
        + os.path.join(args.sources_path, "ORT_icon_for_light_bg.png")
        + '" target="ORT_icon_for_light_bg.png" />'
    )
    files_list.append("</files>")

    list += files_list


def generate_nuspec(args):
    lines = ['<?xml version="1.0"?>']
    lines.append("<package>")
    generate_metadata(lines, args)
    generate_files(lines, args)
    lines.append("</package>")
    return lines


def is_windows():
    return sys.platform.startswith("win")


def is_linux():
    return sys.platform.startswith("linux")


def is_macos():
    return sys.platform.startswith("darwin")


def validate_platform():
    if not (is_windows() or is_linux() or is_macos()):
        raise Exception("Native Nuget generation is currently supported only on Windows, Linux, and MacOS")


def validate_execution_provider(execution_provider):
    if is_linux():
        if not (
            execution_provider == "None"
            or execution_provider == "dnnl"
            or execution_provider == "cuda"
            or execution_provider == "tensorrt"
            or execution_provider == "openvino"
        ):
            raise Exception(
                "On Linux platform nuget generation is supported only "
                "for cpu|cuda|dnnl|tensorrt|openvino execution providers."
            )


def main():
    # Parse arguments
    args = parse_arguments()

    validate_platform()

    validate_execution_provider(args.execution_provider)

    if args.is_release_build.lower() != "true" and args.is_release_build.lower() != "false":
        raise Exception("Only valid options for IsReleaseBuild are: true and false")

    # Generate nuspec
    lines = generate_nuspec(args)

    # Create the nuspec needed to generate the Nuget
    with open(os.path.join(args.native_build_path, "NativeNuget.nuspec"), "w") as f:
        for line in lines:
            # Uncomment the printing of the line if you need to debug what's produced on a CI machine
            # print(line)
            f.write(line)
            f.write("\n")


if __name__ == "__main__":
    sys.exit(main())
