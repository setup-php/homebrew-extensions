require File.expand_path("../Abstract/abstract-php-extension", __dir__)

class PsrAT82 < AbstractPhpExtension
  init
  desc "PHP extension providing the accepted PSR interfaces "
  homepage "https://github.com/jbboehr/php-psr"
  url "https://pecl.php.net/get/psr-1.2.0.tgz"
  sha256 "9c3d2a0d9770916d86e2bc18dfe6513ad9b2bfe00f0d03c1531ef403bee38ebe"
  head "https://github.com/jbboehr/php-psr.git"
  license "BSD-2-Clause"

  bottle do
    root_url "https://ghcr.io/v2/shivammathur/extensions"
    rebuild 1
    sha256 cellar: :any_skip_relocation, arm64_monterey: "22fcf651058614267b8732f97a487df17d2b84f672b168fbb9cdf50c5b268540"
    sha256 cellar: :any_skip_relocation, arm64_big_sur:  "6722f9a9a0261be64a8298eb50dd5c04d1010909c75aa8bbfd6932ed6dc49766"
    sha256 cellar: :any_skip_relocation, ventura:        "eb25866b014bc0dd969be0992f525382cb074c177abd3b4a7fefe7fc0d12238b"
    sha256 cellar: :any_skip_relocation, monterey:       "7fa9a737fa46cb182d8242a642005ea1e901966f3e6afe1cd57ee281b997c6ca"
    sha256 cellar: :any_skip_relocation, big_sur:        "e4b7f6d6342fb595562e25884f7fbba177de0caae7c792ecb4806eb7dfb6b362"
    sha256 cellar: :any_skip_relocation, catalina:       "9d9986471204b0fb8040744142aa9f29f20a8ffdac7931f0f3d64849b54a1b78"
    sha256 cellar: :any_skip_relocation, x86_64_linux:   "53f4b79416711ad5acfeaac438769474673dee165ed81fbcce7bdb6966978481"
  end

  depends_on "pcre"

  def install
    Dir.chdir "psr-#{version}"
    safe_phpize
    system "./configure", "--prefix=#{prefix}", phpconfig, "--enable-psr"
    system "make"
    prefix.install "modules/psr.so"
    write_config_file
  end
end
