# typed: false
# frozen_string_literal: true

require File.expand_path("../Abstract/abstract-php-extension", __dir__)

# Class for Pdo_sqlsrv Extension
class PdoSqlsrvAT73 < AbstractPhpExtension
  init
  desc "pdo_sqlsrv PHP extension"
  homepage "https://github.com/Microsoft/msphpsql"
  url "https://pecl.php.net/get/pdo_sqlsrv-5.11.0.tgz"
  sha256 "c307d9bcada02bdc21f59b9f099031b90b30727757bca50fd42fd36159812e8a"
  head "https://github.com/Microsoft/msphpsql.git"
  license "MIT"

  bottle do
    root_url "https://ghcr.io/v2/shivammathur/extensions"
    sha256 cellar: :any,                 arm64_monterey: "4e199d2c36a28f344ffefb3c30809d06960f5f4508d3f30dee8f2890889aa3ed"
    sha256 cellar: :any,                 arm64_big_sur:  "80cf713f4285dd3b569575d242ffe9c177a75195b752f2311077833f7dbd3648"
    sha256 cellar: :any,                 monterey:       "a27168e4277b48adb093c2d765db2bb4355c56254a88e621aa522f15384a6510"
    sha256 cellar: :any,                 big_sur:        "6fb2592fb18c2c3ad7e2b28f209e3c20a1b2606e5f1d67ae23d9da7586934987"
    sha256 cellar: :any_skip_relocation, x86_64_linux:   "0f8b462449c9ead3051d739f804002e571fe4d791b4bbf76c0cd47c77a905036"
  end

  depends_on "unixodbc"

  def install
    Dir.chdir "pdo_sqlsrv-#{version}"
    safe_phpize
    system "./configure", "--prefix=#{prefix}", phpconfig, "--with-pdo_sqlsrv"
    system "make"
    prefix.install "modules/#{extension}.so"
    write_config_file
    add_include_files
  end
end
