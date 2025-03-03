# typed: true
# frozen_string_literal: true

require File.expand_path("../Abstract/abstract-php-extension", __dir__)

# Class for Zstd Extension
class ZstdAT73 < AbstractPhpExtension
  init
  desc "Zstd Extension for PHP"
  homepage "https://github.com/kjdev/php-ext-zstd"
  url "https://pecl.php.net/get/zstd-0.13.3.tgz"
  sha256 "e4dfa6e5501736f2f5dbfedd33b214c0c47fa98708f0a7d8c65baa95fd6d7e06"
  head "https://github.com/kjdev/php-ext-zstd.git", branch: "master"
  license "MIT"

  bottle do
    root_url "https://ghcr.io/v2/shivammathur/extensions"
    sha256 cellar: :any,                 arm64_sequoia: "15a474c9c754425f427371ff994360514e4fb8251494e08aa850dafbe8e4e02a"
    sha256 cellar: :any,                 arm64_sonoma:  "c6d8d17ee33bf79ff5ea686c52ca0ff07fef7097a9a3e5e262ee75f35063c207"
    sha256 cellar: :any,                 arm64_ventura: "072fdec150be5d134589a0054c0ba45fdf6894a024d09d61f0178c2529ae1342"
    sha256 cellar: :any,                 ventura:       "6c891ae7ec83b5f31ecb4f359617f5595d2fcb221c977df172e729b34f8d9e5f"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "0cca6a0bb5b8cdad5bfb4fa3457b64b120c88932631af8d55f11c6aeb7b019cf"
  end

  depends_on "zstd"

  def install
    Dir.chdir "zstd-#{version}"
    safe_phpize
    system "./configure", "--prefix=#{prefix}", "--with-libzstd", phpconfig
    system "make"
    prefix.install "modules/#{extension}.so"
    write_config_file
    add_include_files
  end
end
